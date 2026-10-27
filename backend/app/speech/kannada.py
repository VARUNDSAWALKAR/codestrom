"""Independent Kannada beat adapter; existing Kokoro pipeline stays unchanged."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from ..cache import variant_key
from ..jobs import PipelineError
from .audio import SAMPLE_RATE, process_audio, read_clip, write_wav
from .kn_textnorm import normalize_kannada
from .parler_engine import ParlerEngine, SPEAKERS

if TYPE_CHECKING:
    from .engines import NarrationContext


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run_kannada_voice(ctx: NarrationContext) -> NarrationContext:
    from .engines import BeatAudio, audio_key
    from ..timeline.schema import Voice
    if not isinstance(ctx.engine, ParlerEngine):
        raise PipelineError("voice_unavailable", "Kannada requires the Parler engine")
    if (ctx.language != "kn" or ctx.lesson.language != "kn" or ctx.lesson.lesson_id != ctx.job.lesson_id
            or ctx.job.variant != variant_key("kn", ctx.gender, ctx.speed)):
        raise PipelineError("tts_identity_mismatch", "Kannada job, lesson, language or variant identity mismatch")
    engine = ctx.engine
    try:
        with engine.session():
            ctx.voice = Voice(engine="parler", voice_id=SPEAKERS[ctx.gender], speed=ctx.speed)
            # Original Kokoro audio_key remains unchanged. Canonical identity is
            # part of Kannada engine_version so tempo-adjusted clips stay isolated too.
            ctx.engine_version = f"{engine.engine_version}:lesson={ctx.lesson.lesson_id}"
            ctx.cache.initialize()
            clips = []
            for scene in ctx.lesson.scenes:
                beats = ([(None, scene.narration)] if scene.narration.strip() else [])
                beats += [(i, step.narration) for i, step in enumerate(scene.steps)]
                for index, narration in beats:
                    beat_id = f"{scene.id}." + ("intro" if index is None else f"step{index}")
                    speech = normalize_kannada(narration)
                    text_identity = json.dumps([narration, speech], ensure_ascii=False)
                    key = audio_key(text_identity, "kn", "parler", ctx.voice.voice_id, ctx.speed, 1.0, ctx.engine_version)
                    path, manifest = ctx.cache.audio / f"{key}.wav", ctx.cache.audio / f"{key}.kn.json"
                    spec = {"lesson_id": ctx.lesson.lesson_id, "narration": narration, "speech": speech,
                            "lang": "kn", "engine": ctx.engine_version, "voice": ctx.voice.voice_id, "speed": ctx.speed}
                    cached = path.is_file()
                    if cached:
                        try:
                            metadata = json.loads(manifest.read_text(encoding="utf-8"))
                            samples = read_clip(path)
                            if (metadata["spec"] != spec or metadata["sha256"] != _hash(path)
                                    or metadata["samples"] != len(samples) or metadata["sample_rate"] != SAMPLE_RATE):
                                raise ValueError("Audio cache provenance/hash mismatch")
                        except (OSError, ValueError, KeyError, RuntimeError) as exc:
                            raise PipelineError("tts_cache_invalid", f"Kannada beat {beat_id}: {exc}") from exc
                    else:
                        raw, rate = engine.synthesize(speech, "kn", ctx.voice.voice_id, ctx.speed)
                        samples = process_audio(raw, rate, ctx.settings.ffmpeg)
                        write_wav(path, samples)
                        samples = read_clip(path)
                        ctx.cache.write_json(manifest, {"spec": spec, "sha256": _hash(path),
                                                       "samples": len(samples), "sample_rate": SAMPLE_RATE})
                    clips.append(BeatAudio(beat_id=beat_id, scene_id=scene.id, step_index=index,
                        narration=narration, speech_text=speech, path=path, samples=len(samples), cache_key=key, cached=cached))
            ctx.clips = clips
            stage = next(s for s in ctx.job.stages if s.name == "voice")
            stage.status = "cached" if all(c.cached for c in clips) else "done"
            stage.note = (f"Parler/{ctx.voice.voice_id}; {len(clips)} beats; {sum(c.cached for c in clips)} cached; "
                          f"{sum(c.samples for c in clips)/SAMPLE_RATE:.3f}s speech")
            return ctx
    finally:
        if ctx.settings.low_ram:
            engine.release()  # waits until all sessions/inference have left the lock
