"""Approved Suresh profile: no model weights/inference, real RNG and temporary audio caches."""
import json
import random
from dataclasses import replace
import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.contracts import LessonRequest
from backend.app.language_policy import approved_languages, approved_voices
from backend.app import pipeline_ops
from backend.app.main import create_app
from backend.app.speech.engines import run_voice
from backend.app.speech.parler_engine import SEQUENCE_POLICY
from backend.tests.test_task7 import FakeParler, context


@pytest.fixture
def config(tmp_path):
    return Settings(device="cpu", cache_dir=tmp_path/"cache", approved_languages=("en", "hi", "kn"),
                    parler_seed=21, parler_max_new_tokens=1500)


@pytest.mark.parametrize("seed,cap,enabled,available", [(21,1500,True,True),(7,1500,True,False),
    (21,2400,True,False),(21,1500,False,False)])
def test_approved_profile_gate(config, seed, cap, enabled, available):
    settings=config.model_copy(update=dict(parler_seed=seed,parler_max_new_tokens=cap,enable_parler=enabled))
    assert ("kn" in approved_languages(settings)) == available
    assert approved_voices(settings,"kn") == (("male",) if available else ())
    for lang in ("en","hi"):
        for voice in ("female","male"):
            pipeline_ops.precheck(LessonRequest(topic="Water Cycle",language=lang,voice=voice),settings)


def test_config_and_real_precheck_reject_unapproved_female_before_work(config):
    # Production precheck runs on real API requests; none of the rejected requests reach a stage.
    with TestClient(create_app(config)) as client:
        value=client.get('/api/config').json()
        assert all(v['available'] for v in value['languages'] if v['code'] in {'en','hi','kn'})
        assert value['voice_options']['kn'] == [dict(voice='male',speaker='Suresh',engine='parler',seed=21,seed_policy=SEQUENCE_POLICY)]
        assert [v['voice'] for v in value['voice_options']['hi']] == ['female','male']
        for body in (dict(topic='Water Cycle',language='kn',voice='female'),dict(topic='Water Cycle',language='kn')):
            response=client.post('/api/lessons',json=body)
            assert response.status_code == 422 and response.json()['error']['code']=='voice_unavailable'
        for level in ('beginner','intermediate'):
            for speed in (.85,1,1.15):
                request=LessonRequest(topic='Water Cycle',language='kn',voice='male',level=level,speed=speed)
                pipeline_ops.precheck(request,config)
                assert request.level==level and request.speed==speed


class RandomParler(FakeParler):
    def _load_components(self):
        random.random();np.random.random();torch.rand(1)  # load must precede seeding
        return super()._load_components()

    def _generate(self,text,speaker):
        self.load();self.calls+=1
        # Stand-in generation consumes each RNG that transformers.set_seed controls.
        draws=(random.random(),float(np.random.random()),float(torch.rand(1)))
        self.draws.append(draws)
        t=np.arange(2400)/24000
        return (.1*np.sin(2*np.pi*(200+sum(draws)*100)*t)).astype(np.float32),24000


def engine(config):
    value=RandomParler(config);value.draws=[]
    return value


def test_seed_once_original_experiment_order_and_outer_rng_restored(config):
    value=engine(config);value.load()
    python_state=random.getstate();numpy_state=np.random.get_state();torch_state=torch.get_rng_state()
    # Same reference as benchmark_parler.py: set_seed(21) once before sequential S1-S3.
    from transformers import set_seed
    set_seed(21)
    expected=[(random.random(),float(np.random.random()),float(torch.rand(1))) for _ in range(3)]
    random.setstate(python_state);np.random.set_state(numpy_state);torch.set_rng_state(torch_state)
    sentences=['ಇಂದು ನಾವು ನೀರಿನ ಚಕ್ರದ ಬಗ್ಗೆ ಕಲಿಯೋಣ.','ಸೂರ್ಯನ ಶಾಖದಿಂದ ನೀರು ಆವಿಯಾಗಿ ಮೇಲಕ್ಕೆ ಹೋಗುತ್ತದೆ.',
               'ಆವಿ ತಣ್ಣಗಾದಾಗ ಮೋಡಗಳಾಗಿ ಮಳೆಯಾಗಿ ಬೀಳುತ್ತದೆ.']
    for _ in range(2):
        value.draws=[]
        with value.utterance_sequence():
            for sentence in sentences:value.synthesize(sentence,'kn','Suresh',1)
        assert value.draws==expected and len(set(value.draws))==3
        assert random.getstate()==python_state
        assert np.array_equal(np.random.get_state()[1],numpy_state[1])
        assert torch.equal(torch.get_rng_state(),torch_state)


def test_load_before_seed_partial_cache_resume_and_zero_load_cache_hit(config):
    value=engine(config);first=context(config,value,gender='male');run_voice(first)
    draws=list(value.draws);audio=[clip.path.read_bytes() for clip in first.clips]
    assert len(draws)==len(first.clips) and len(set(draws))==len(draws)
    # Only pytest's temporary cache is altered. Resume must skip prior draws via RNG snapshots.
    missing=first.clips[1].path;missing.unlink()
    resumed=engine(config);again=context(config,resumed,gender='male');run_voice(again)
    assert resumed.calls==1 and resumed.draws==[draws[1]]
    assert [clip.path.read_bytes() for clip in again.clips]==audio
    cached=engine(config);last=context(config,cached,gender='male');run_voice(last)
    assert cached.calls==cached.loads==0 and all(clip.cached for clip in last.clips)
    assert first.engine_version==last.engine_version


def test_cache_rng_integrity_and_order_isolation(config):
    value=engine(config);first=context(config,value,gender='male');run_voice(first)
    manifest=first.clips[0].path.with_suffix('.kn.json');payload=json.loads(manifest.read_text(encoding='utf-8'))
    payload['rng_after']['torch'][0]^=1;manifest.write_text(json.dumps(payload), encoding='utf-8')
    with pytest.raises(Exception,match='RNG cache hash mismatch'):
        run_voice(context(config,engine(config),gender='male'))
    changed=first.lesson.model_copy(deep=True);changed.scenes[0].narration+=' ಹೆಚ್ಚುವರಿ ವಿವರಣೆ.'
    other=context(config,engine(config),gender='male',localized=changed);run_voice(other)
    assert all(a.cache_key!=b.cache_key for a,b in zip(first.clips,other.clips))


def test_completed_legacy_kannada_export_requires_voice_provenance(config,monkeypatch,tmp_path):
    from types import SimpleNamespace
    from backend.tests.test_task7 import lesson
    folder=tmp_path/'kn-male-1';folder.mkdir()
    monkeypatch.setattr(pipeline_ops,'mp4_structure_complete',lambda p:True)
    monkeypatch.setattr(pipeline_ops,'check_inputs',lambda p:(lesson(),SimpleNamespace(voice=SimpleNamespace(voice_id='Suresh'))))
    monkeypatch.setattr(pipeline_ops,'localization_artifact_valid',lambda *a:True)
    assert not pipeline_ops.export_complete(folder,config)  # old seed-7 MP4 is never an approved cache hit


def test_seed_and_sequence_policy_version_audio_namespace(config, monkeypatch):
    from backend.app.speech import parler_engine
    from backend.app.speech.engines import audio_key
    from backend.app.speech.parler_engine import ParlerEngine
    # Exercise the real fingerprint without reading multi-GB model assets.
    monkeypatch.setattr(parler_engine, '_assets', lambda files: 'same-local-model-assets')
    monkeypatch.setattr(parler_engine, 'version', lambda name: 'test-installed-version')
    monkeypatch.setattr(parler_engine.Path, 'stat', lambda path: type('Stat', (), dict(st_size=1, st_mtime_ns=1))())
    old = ParlerEngine(config.model_copy(update={'parler_seed': 7})).engine_version
    approved = ParlerEngine(config).engine_version
    assert old != approved
    key = lambda version: audio_key('same text', 'kn', 'parler', 'Suresh', 1, 1, version)
    assert key(old) != key(approved)
    monkeypatch.setattr(parler_engine, 'SEQUENCE_POLICY', 'different-sequence-policy')
    assert ParlerEngine(config).engine_version != approved


def test_real_generation_rng_context_advances_without_reseeding(config):
    value = engine(config)
    with value.utterance_sequence():
        with value._beat_rng([]): first = torch.rand(5)
        with value._beat_rng([]): second = torch.rand(5)
    with torch.random.fork_rng():
        torch.manual_seed(21)
        assert torch.equal(first, torch.rand(5))
        assert torch.equal(second, torch.rand(5))


def test_kannada_export_memo_rechecks_voice_profile(config):
    from backend.app.cache import Cache
    from backend.app.orchestrator import Orchestrator
    cache = Cache(config.cache_dir)
    folder = cache.lesson_dir('c1f63f0ed69b', 'kn-male-1')
    folder.mkdir(parents=True)
    (folder / 'lesson.mp4').write_bytes(b'test-only-not-video')
    profile = folder / 'voice-profile.json'
    profile.write_text('{}', encoding='utf-8')
    checked = []
    ops = replace(pipeline_ops.production_ops(settings=config),
                  export_complete=lambda *args: checked.append(True) or profile.is_file())
    orchestrator = Orchestrator(config, cache, 'cpu', ops)
    assert orchestrator.export_verified(folder)
    assert orchestrator.export_verified(folder) and len(checked) == 1
    profile.unlink()  # pytest temporary folder only
    assert not orchestrator.export_verified(folder) and len(checked) == 2
