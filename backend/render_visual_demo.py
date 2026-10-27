"""Explicit authored demo: existing voice -> measured timeline -> normal MP4 export.

No planner/job-submission route imports this command. All writes stay in --out.
"""
from __future__ import annotations

from .app.config import ROOT, Settings, get_settings

import argparse
import hashlib
import json
import shutil
import socket
import subprocess
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .app.cache import Cache, variant_key
from .app.export.render import ExportContext, render_props, run_export
from .app.jobs import JobRecord, run_measured_stage
from .app.planner.schema import Lesson
from .app.speech.audio import read_clip
from .app.speech.engines import NarrationContext, audio_key, run_voice
from .app.speech.kokoro_engine import KokoroEngine
from .app.speech.textnorm import normalize_text
from .app.timeline.build import run_timeline
from .app.visuals.bind import bind_timeline
from .app.visuals.schema import VisualSpec
from .app.visuals.validate import fingerprint, source_fingerprint, validate_visuals

FIXTURE = ROOT / 'backend/tests/fixtures/visuals/array_grid_demo.json'


def demo_source() -> tuple[Lesson, VisualSpec]:
    raw = json.loads(FIXTURE.read_text(encoding='utf-8'))
    source = Lesson.model_validate(raw['source'])
    # Cache requires a hex ID. Derive a NEW isolated sample identity; never relabel
    # a production plan or pretend these authored words came from an LLM.
    identifier = fingerprint({'demo': 'vq3-narrated-array-v1', 'source': source_fingerprint(source)})[:12]
    lesson = source.model_copy(update={'lesson_id': identifier})
    spec = {**raw['spec'], 'lesson_id': identifier, 'source_fingerprint': source_fingerprint(lesson)}
    checked = validate_visuals(spec, lesson)
    if checked.spec is None:
        raise ValueError('Authored demo failed source validation: ' + str(checked.diagnostics))
    return lesson, checked.spec


def output_cache(out: Path) -> Cache:
    if out.is_relative_to((ROOT / 'cache').resolve()):
        raise ValueError('Use an isolated demo directory, not production cache')
    marker = out / 'controlled-demo.json'
    if out.exists() and any(out.iterdir()) and not marker.is_file():
        raise ValueError('Refusing to overwrite a non-demo output directory')
    out.mkdir(parents=True, exist_ok=True)
    expected = {'kind': 'vq3-authored-array-v1', 'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest()}
    if marker.exists() and json.loads(marker.read_text()) != expected:
        raise ValueError('Existing demo directory has a different fixture')
    marker.write_text(json.dumps(expected, indent=2), encoding='utf-8')
    cache = Cache(out / 'cache')
    cache.initialize()
    return cache


def reuse_exact_audio(source: Path | None, ctx: NarrationContext) -> int:
    if source is None:
        return 0
    copied = 0
    for scene in ctx.lesson.scenes:
        texts = ([scene.narration] if scene.narration.strip() else []) + [s.narration for s in scene.steps]
        for text in texts:
            key = audio_key(normalize_text(text, 'en'), 'en', 'kokoro', ctx.settings.kokoro_voice_female,
                            1.0, 1.0, ctx.engine.engine_version)
            candidate, target = source / f'{key}.wav', ctx.cache.audio / f'{key}.wav'
            if candidate.is_file() and not target.exists():
                read_clip(candidate)  # Validate before read-only reuse.
                shutil.copyfile(candidate, target)
                copied += 1
    return copied


def reserve_media_socket() -> socket.socket:
    for port in (8000, 3000):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('127.0.0.1', port))
            sock.listen(32)
            return sock
        except OSError:
            sock.close()
    raise RuntimeError('Local media ports 8000 and 3000 are occupied; existing services were left alone')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reuse-audio-cache', type=Path)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    if args.reuse_audio_cache and out.is_relative_to(args.reuse_audio_cache.resolve().parent):
        raise ValueError('Demo output must be separate from the reused production cache')
    cache = output_cache(out)
    lesson, spec = demo_source()
    media_socket = reserve_media_socket()
    settings: Settings = get_settings().model_copy(update={'device': 'cpu', 'cache_dir': cache.root,
        'port': media_socket.getsockname()[1], 'render_concurrency': 2})
    job = JobRecord(lesson_id=lesson.lesson_id, variant=variant_key('en', 'female', 1), device_profile='cpu')
    voice = NarrationContext(job=job, language='en', lesson=lesson, settings=settings,
                             cache=cache, engine=KokoroEngine(settings))
    report = {'kind': 'controlled authored narrated demo; NOT automatic topic-to-visual generation',
        'original_fixture_id': 'sample-vq1-binary-array', 'isolated_lesson_id': lesson.lesson_id,
        'checkpoint': 'source-only checkpoint created before VQ3', 'planner_calls': 0,
        'copied_exact_audio_clips': reuse_exact_audio(args.reuse_audio_cache, voice)}
    try:
        for name, operation in [('voice', run_voice), ('timeline', run_timeline)]:
            run_measured_stage(voice, name, operation, cache)
            print(json.dumps({'stage': name, **next(s for s in job.stages if s.name == name).model_dump()}), flush=True)
        assert voice.timeline is not None
        folder = cache.lesson_dir(lesson.lesson_id, job.variant)
        report['beats'] = [c.model_dump(mode='json') for c in voice.clips]
        report['actions'] = [a.model_dump() for a in bind_timeline(spec, lesson, lesson, voice.timeline)]
        report['timeline_frames'] = voice.timeline.duration_frames
        report['tempo'] = voice.timeline.tempo
        props = render_props(lesson, voice.timeline, settings, visual_spec=spec.model_dump(mode='json'))
        assert props.visualSpec is not None
        cache.write_json(folder / 'visual.props.json', props)
        app = FastAPI(docs_url=None, redoc_url=None)
        app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173'], allow_methods=['GET', 'HEAD'])
        app.mount('/media', StaticFiles(directory=cache.lessons), name='demo-media')

        @app.get('/demo/props')
        def demo_props():
            return JSONResponse(props.model_dump(mode='json'))

        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=settings.port, log_level='error', access_log=False))
        thread = Thread(target=lambda: server.run(sockets=[media_socket]), daemon=True)
        thread.start()
        try:
            deadline = monotonic() + 10
            while not server.started and thread.is_alive() and monotonic() < deadline:
                sleep(.05)
            if not server.started:
                raise RuntimeError('Isolated media server failed to start')
            ctx = ExportContext(job=job, language='en', settings=settings, cache=cache,
                                visual_spec=spec.model_dump(mode='json'))
            run_measured_stage(ctx, 'export', run_export, cache)
            print(json.dumps({'stage': 'export', **next(s for s in job.stages if s.name == 'export').model_dump()}), flush=True)
            shutil.copyfile(folder / 'lesson.mp4', out / 'lesson.mp4')
            report.update(mp4=str(out / 'lesson.mp4'), variant_folder=str(folder), warnings=job.warnings,
                          stages=[s.model_dump() for s in job.stages], media_port=settings.port)
            if args.verify:
                script = ROOT / 'web/scripts/verify-narrated-visual.mjs'
                subprocess.run([settings.node_binary, '--import', 'tsx', str(script), str(folder / 'visual.props.json'), str(out / 'verification')],
                               cwd=ROOT / 'web', check=True)
        finally:
            server.should_exit = True
            thread.join(10)
        report['ok'] = True
    except Exception as exc:
        report.update(ok=False, error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        media_socket.close()
        (out / 'acceptance.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'ok': True, 'mp4': report['mp4'], 'report': str(out / 'acceptance.json')}), flush=True)


if __name__ == '__main__':
    main()
