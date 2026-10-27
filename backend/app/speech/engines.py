"""English/Hindi engine selection and the independent voice pipeline stage."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from ..cache import Cache, variant_key
from ..config import Settings
from ..jobs import JobContext
from ..planner.schema import Lesson
from ..timeline.schema import Timeline, Voice
from .audio import read_clip, process_audio, write_wav, SAMPLE_RATE
from .kokoro_engine import KokoroEngine
from .textnorm import normalize_text


class BeatAudio(BaseModel):
    beat_id: str
    scene_id: str
    step_index: int | None
    narration: str
    speech_text: str
    path: Path
    samples: int = Field(gt=0)
    cache_key: str
    cached: bool


class NarrationContext(JobContext):
    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)
    lesson: Lesson
    settings: Settings
    cache: Cache
    engine: KokoroEngine
    gender: Literal["female", "male"] = "female"
    speed: float = Field(default=1.0, ge=0.8, le=1.2)
    clips: list[BeatAudio] = Field(default_factory=list)
    voice: Voice | None = None
    timeline: Timeline | None = None
    engine_version: str = ""


def audio_key(text: str, language: str, engine: str, voice_id: str,
              speed: float, tempo: float, engine_version: str) -> str:
    value = "|".join((text, language, engine, voice_id, f"{speed:g}", f"{tempo:.12g}", engine_version))
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def run_voice(ctx: NarrationContext) -> NarrationContext:
    if ctx.lesson.language not in {"en", "hi"}:
        raise ValueError("Task 2 voices support only English and Hindi; translation is not implemented")
    if ctx.language != ctx.lesson.language or ctx.job.lesson_id != ctx.lesson.lesson_id:
        raise ValueError("Job and lesson identity mismatch")
    if ctx.job.variant != variant_key(ctx.language, ctx.gender, ctx.speed):
        raise ValueError("Job variant does not match voice request")
    ctx.voice = Voice(engine="kokoro", voice_id=(ctx.settings.kokoro_voice_female if ctx.gender == "female"
                                              else ctx.settings.kokoro_voice_male), speed=ctx.speed)
    ctx.engine_version = ctx.engine.engine_version
    ctx.cache.initialize()
    clips: list[BeatAudio] = []
    for scene in ctx.lesson.scenes:
        beats = ([(None, scene.narration)] if scene.narration.strip() else [])
        beats += [(i, s.narration) for i, s in enumerate(scene.steps)]
        for index, narration in beats:
            beat_id = f"{scene.id}." + ("intro" if index is None else f"step{index}")
            speech_text = normalize_text(narration, ctx.language)
            key = audio_key(speech_text, ctx.language, "kokoro", ctx.voice.voice_id,
                            ctx.speed, 1.0, ctx.engine_version)
            path = ctx.cache.audio / f"{key}.wav"
            cached = path.is_file()
            if cached:
                samples = read_clip(path)  # Corrupt cache is an explicit error, not silent replacement.
            else:
                try:
                    raw, rate = ctx.engine.synthesize(speech_text, ctx.language, ctx.voice.voice_id, ctx.speed)
                    samples = process_audio(raw, rate, ctx.settings.ffmpeg)
                    write_wav(path, samples)
                except Exception as exc:
                    raise RuntimeError(f"Voice beat {beat_id} failed; no alternative engine is implemented in Task 2: {exc}") from exc
            clips.append(BeatAudio(beat_id=beat_id, scene_id=scene.id, step_index=index,
                                   narration=narration, speech_text=speech_text, path=path,
                                   samples=len(samples), cache_key=key, cached=cached))
    ctx.clips = clips
    stage = next(s for s in ctx.job.stages if s.name == "voice")
    stage.status = "cached" if all(c.cached for c in clips) else "done"
    stage.note = f"{len(clips)} beats; {sum(c.cached for c in clips)} cached; {sum(c.samples for c in clips) / SAMPLE_RATE:.3f}s speech"
    return ctx
