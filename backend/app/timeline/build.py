"""Audio-derived timeline stage. All arithmetic accumulates in audio samples."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from pydantic import BaseModel

from ..speech.audio import SAMPLE_RATE, read_clip, write_wav, encode_m4a, change_tempo
from ..speech.engines import NarrationContext, BeatAudio, audio_key
from .captions import build_captions
from .schema import AudioURLs, Beat, SceneTiming, Timeline, RenderProps
from .srt import render_srt

LEAD_IN = round(0.30 * SAMPLE_RATE)
BEAT_GAP = round(0.25 * SAMPLE_RATE)
SCENE_TAIL = round(0.60 * SAMPLE_RATE)
TITLE_MIN = round(2.5 * SAMPLE_RATE)
MAX_LESSON = 90
TIMING_VERSION = "samples-v1"


class ArtifactManifest(BaseModel):
    fingerprint: str
    hashes: dict[str, str]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def schedule(ctx: NarrationContext, clips: list[BeatAudio]) -> tuple[list[SceneTiming], dict[str, int], int]:
    time = 0
    starts: dict[str, int] = {}
    scenes = []
    fps = ctx.settings.export_fps
    frame = lambda samples: round(samples * fps / SAMPLE_RATE)
    for scene in ctx.lesson.scenes:
        selected = [clip for clip in clips if clip.scene_id == scene.id]
        if not selected:
            raise ValueError(f"No narration clips for {scene.id}")
        scene_start = time
        time += LEAD_IN
        beats = []
        for clip in selected:
            starts[clip.beat_id] = time
            end = time + clip.samples
            beats.append(Beat(beat_id=clip.beat_id, step_index=clip.step_index,
                              start_frame=frame(time), end_frame=frame(end),
                              captions=build_captions(clip.narration, ctx.language, frame(time), frame(end))))
            time = end + BEAT_GAP
        time += SCENE_TAIL - BEAT_GAP
        if scene.type == "title_card":
            time = max(time, scene_start + TITLE_MIN)
        scenes.append(SceneTiming(scene_id=scene.id, type=scene.type, start_frame=frame(scene_start),
                                  duration_frames=frame(time) - frame(scene_start), beats=beats))
    return scenes, starts, time


def run_timeline(ctx: NarrationContext) -> NarrationContext:
    if not ctx.clips or ctx.voice is None:
        raise ValueError("Voice stage must supply measured clips before timeline")
    output = ctx.cache.lesson_dir(ctx.lesson.lesson_id, ctx.job.variant)
    output.mkdir(parents=True, exist_ok=True)
    # Re-measure every input WAV; never trust a stale duration in a context.
    clips = [clip.model_copy(update={"samples": len(read_clip(clip.path))}) for clip in ctx.clips]
    fingerprint = hashlib.sha256(json.dumps({
        "lesson": ctx.lesson.model_dump(mode="json"), "variant": ctx.job.variant,
        "voice": ctx.voice.model_dump(), "timing": TIMING_VERSION,
        "clips": [(c.beat_id, digest(c.path)) for c in clips],
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    manifest_path = output / "audio-manifest.json"
    stage = next(s for s in ctx.job.stages if s.name == "timeline")
    if manifest_path.is_file():
        manifest = ArtifactManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        required = {"timeline.json", "narration.wav", "narration.m4a", "lesson.srt", "lesson.json", "props.json"}
        if (manifest.fingerprint == fingerprint and set(manifest.hashes) == required
                and all((output / name).is_file() and digest(output / name) == checksum
                        for name, checksum in manifest.hashes.items())):
            timeline = Timeline.model_validate_json((output / "timeline.json").read_text(encoding="utf-8"))
            RenderProps(lesson=ctx.lesson, timeline=timeline)
            ctx.timeline = timeline
            ctx.job.playable = True
            stage.status = "cached"
            stage.note = "Validated cached narration, captions and timeline"
            return ctx

    scenes, starts, total_samples = schedule(ctx, clips)
    tempo = 1.0
    if total_samples > MAX_LESSON * SAMPLE_RATE:
        speech_samples = sum(c.samples for c in clips)
        pause_samples = total_samples - speech_samples
        available = MAX_LESSON * SAMPLE_RATE - pause_samples
        tempo = min(1.10, speech_samples / available) if available > 0 else 1.10
        adjusted = []
        for clip in clips:
            key = audio_key(clip.speech_text, ctx.language, ctx.voice.engine, ctx.voice.voice_id,
                            ctx.speed, tempo, ctx.engine_version)
            path = ctx.cache.audio / f"{key}.wav"
            if not path.is_file():
                change_tempo(clip.path, path, tempo, ctx.settings.ffmpeg)
            adjusted.append(clip.model_copy(update={"path": path, "samples": len(read_clip(path)), "cache_key": key}))
        clips = adjusted
        scenes, starts, total_samples = schedule(ctx, clips)
    duration_frames = sum(s.duration_frames for s in scenes)
    if duration_frames / ctx.settings.export_fps > MAX_LESSON:
        warning = "Lesson exceeds 90 seconds after maximum 1.10 tempo adjustment"
        if warning not in ctx.job.warnings:
            ctx.job.warnings.append(warning)
    prefix = f"/media/{ctx.lesson.lesson_id}/{ctx.job.variant}"
    timeline = Timeline(lesson_id=ctx.lesson.lesson_id, language=ctx.language, variant=ctx.job.variant,
                        duration_frames=duration_frames, audio=AudioURLs(web=f"{prefix}/narration.m4a",
                        wav=f"{prefix}/narration.wav"), voice=ctx.voice, tempo=tempo, scenes=scenes)
    props = RenderProps(lesson=ctx.lesson, timeline=timeline)
    narration = np.zeros(round(duration_frames * SAMPLE_RATE / timeline.fps), dtype=np.float32)
    for clip in clips:
        audio = read_clip(clip.path)
        start = starts[clip.beat_id]
        if start + len(audio) > len(narration):
            raise ValueError("Narration audio exceeds timeline buffer")
        narration[start:start + len(audio)] = audio
    write_wav(output / "narration.wav", narration)
    encode_m4a(output / "narration.wav", output / "narration.m4a", ctx.settings.ffmpeg)
    (output / "lesson.srt").write_text(render_srt(timeline), encoding="utf-8")
    ctx.cache.write_json(output / "lesson.json", ctx.lesson)
    ctx.cache.write_json(output / "props.json", props)
    ctx.cache.write_json(output / "timeline.json", timeline)
    names = ("timeline.json", "narration.wav", "narration.m4a", "lesson.srt", "lesson.json", "props.json")
    ctx.cache.write_json(manifest_path, ArtifactManifest(fingerprint=fingerprint,
                         hashes={name: digest(output / name) for name in names}))
    ctx.timeline = timeline
    ctx.job.playable = True
    stage.status = "done"
    stage.note = f"{duration_frames} frames; tempo {tempo:.6g}; {sum(c.samples for c in clips) / SAMPLE_RATE:.3f}s speech"
    return ctx
