"""Optional authored VisualSpec integration, no inference or real export."""
import hashlib
import json

import pytest

from backend.app.config import get_settings
from backend.app.export.render import render_props, props_sha1
from backend.app.timeline.schema import Timeline, RenderProps
from backend.app.visuals.validate import validate_visuals
from backend.render_visual_demo import demo_source
from backend.tests.test_task2 import ctx_for, fake_clips
from backend.app.timeline.build import schedule


@pytest.fixture
def demo(tmp_path):
    lesson, spec = demo_source()
    ctx = ctx_for(lesson)
    scenes, _, _ = schedule(ctx, fake_clips(lesson, tmp_path, .7))
    prefix = f'/media/{lesson.lesson_id}/en-female-1'
    timeline = Timeline(lesson_id=lesson.lesson_id, language='en', variant='en-female-1',
        duration_frames=sum(s.duration_frames for s in scenes), scenes=scenes,
        audio={'web': prefix+'/narration.m4a', 'wav': prefix+'/narration.wav'},
        voice={'engine': 'kokoro', 'voice_id': 'hf_alpha', 'speed': 1.0})
    return lesson, spec, timeline


def test_demo_derives_isolated_identity_without_rewriting_authored_content(demo):
    from backend.render_visual_demo import FIXTURE
    source=json.loads(FIXTURE.read_text())['source']
    lesson,spec,_=demo
    assert lesson.lesson_id!='sample-vq1-binary-array'
    normalized=lesson.model_dump(mode='json');normalized['lesson_id']=source['lesson_id']
    assert normalized==source
    assert validate_visuals(spec,lesson).spec is not None
    assert demo_source()[0].lesson_id==lesson.lesson_id


def test_absent_optional_sidecar_preserves_legacy_json_and_cache_key(demo):
    lesson,_,timeline=demo
    props=render_props(lesson,timeline,get_settings())
    legacy=props.model_dump(mode='json')
    assert 'visualSpec' not in legacy and 'visualSpec' not in json.loads(props.model_dump_json())
    assert set(legacy)=={'lesson','timeline','mediaBase','audioVariant','showCaptions'}
    assert props_sha1(props)==hashlib.sha1(json.dumps(legacy,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    assert RenderProps.model_validate(legacy).model_dump(mode='json')==legacy


def test_validated_sidecar_reaches_export_props_and_changes_media_identity(demo):
    lesson,spec,timeline=demo
    plain=render_props(lesson,timeline,get_settings())
    visual=render_props(lesson,timeline,get_settings(),visual_spec=spec.model_dump(mode='json'))
    assert visual.visualSpec==spec.model_dump(mode='json')
    assert props_sha1(visual)!=props_sha1(plain)
    assert visual.lesson==plain.lesson and visual.timeline==plain.timeline
    changed=spec.model_dump(mode='json');changed['scenes'][1]['actions'][0]['end']=.7
    another=render_props(lesson,timeline,get_settings(),visual_spec=changed)
    assert another.visualSpec is not None and props_sha1(another)!=props_sha1(visual)


@pytest.mark.parametrize('mutation',['version','source','object','beat','identity','not_object'])
def test_invalid_visual_sidecar_is_dropped_for_legacy_export(demo,mutation):
    lesson,spec,timeline=demo;raw=spec.model_dump(mode='json')
    if mutation=='version':raw['visual_schema_version']='visual-v99'
    if mutation=='source':raw['source_fingerprint']='0'*64
    if mutation=='object':raw['scenes'][1]['objects'][0]['kind']='html'
    if mutation=='beat':raw['scenes'][1]['actions'][0]['beat_id']='s2.step5'
    if mutation=='identity':raw['lesson_id']='000000000000'
    if mutation=='not_object':raw=['invalid']
    props=render_props(lesson,timeline,get_settings(),visual_spec=raw)
    assert props.visualSpec is None and 'visualSpec' not in props.model_dump()


def test_automatic_planning_and_production_demo_injection_remain_absent():
    from backend.app.config import ROOT
    for name in ['backend/app/pipeline_ops.py','backend/app/orchestrator.py','backend/app/main.py']:
        source=(ROOT/name).read_text()
        assert 'render_visual_demo' not in source and 'plan_semantic_visuals' not in source and 'visuals.joint' not in source
