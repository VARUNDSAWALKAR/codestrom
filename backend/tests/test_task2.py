"""Task 2 tests: fast and deterministic. Real Kokoro is only exercised by generate_narration."""
from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from backend.app.cache import Cache, variant_key
from backend.app.config import ROOT, get_settings
from backend.app.jobs import JobRecord
from backend.app.planner.schema import Lesson
from backend.app.speech import audio
from backend.app.speech.audio import SAMPLE_RATE, process_audio, read_clip, write_wav
from backend.app.speech.engines import BeatAudio, NarrationContext, audio_key
from backend.app.speech.textnorm import normalize_text
from backend.app.timeline.build import BEAT_GAP, LEAD_IN, SCENE_TAIL, TITLE_MIN, schedule
from backend.app.timeline.captions import build_captions, chunks
from backend.app.timeline.schema import Beat, RenderProps, Timeline
from backend.app.timeline.srt import render_srt, timestamp

FALLBACK = ROOT / "data" / "fallback" / "python_loop.en.json"
HAVE_FFMPEG = shutil.which(get_settings().ffmpeg) is not None


@pytest.fixture(scope="module")
def lesson() -> Lesson:
    return Lesson.model_validate_json(FALLBACK.read_text(encoding="utf-8"))


def tone(seconds: float, rate: int = SAMPLE_RATE, amp: float = 0.3) -> np.ndarray:
    t = np.arange(round(seconds * rate)) / rate
    return (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def fake_clips(lesson: Lesson, tmp: Path, seconds: float = 2.0) -> list[BeatAudio]:
    clips = []
    for scene in lesson.scenes:
        beats = ([(None, scene.narration)] if scene.narration.strip() else [])
        beats += [(i, s.narration) for i, s in enumerate(scene.steps)]
        for index, text in beats:
            beat_id = f"{scene.id}." + ("intro" if index is None else f"step{index}")
            clips.append(BeatAudio(beat_id=beat_id, scene_id=scene.id, step_index=index, narration=text,
                                   speech_text=text, path=tmp / f"{beat_id}.wav", samples=round(seconds * SAMPLE_RATE),
                                   cache_key="k", cached=False))
    return clips


def ctx_for(lesson: Lesson) -> NarrationContext:
    settings = get_settings()
    return NarrationContext.model_construct(
        job=JobRecord(lesson_id=lesson.lesson_id, variant=variant_key("en", "female", 1), device_profile="cpu"),
        language="en", lesson=lesson, settings=settings)


# ---- text normalisation ----
def test_normalize_strips_markup_and_adds_period():
    assert normalize_text("A `for` loop (repeats)", "en") == "A for loop repeats."


def test_normalize_keeps_terminal_punctuation_and_hindi_danda():
    assert normalize_text("Done!", "en") == "Done!"
    assert normalize_text("नमस्ते", "hi").endswith("।")


def test_normalize_rejects_empty():
    with pytest.raises(ValueError):
        normalize_text(" ()  ", "en")


# ---- engine config ----
def test_kokoro_config_resolves_to_local_hf_alpha():
    s = get_settings()
    assert s.kokoro_voice_female == "hf_alpha"
    assert s.kokoro_model.is_file() and s.kokoro_voices.is_file()


def test_kokoro_rejects_unsupported_language():
    from backend.app.speech.kokoro_engine import KokoroEngine
    with pytest.raises(ValueError):
        KokoroEngine(get_settings()).synthesize("x", "kn", "hf_alpha", 1.0)


# ---- audio processing ----
@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg missing")
def test_resample_to_24k_and_normalise():
    out = process_audio(tone(1.0, 16000, 0.05), 16000, get_settings().ffmpeg)
    assert abs(len(out) - SAMPLE_RATE) < SAMPLE_RATE * 0.02  # 16k -> 24k, padding is clamped to the clip
    assert np.abs(out).max() <= 10 ** (-1 / 20) + 1e-6
    assert abs(np.sqrt(np.mean(out ** 2)) - 0.1) < 0.02


def test_trim_silence_keeps_padding():
    x = np.concatenate([np.zeros(SAMPLE_RATE), tone(0.5), np.zeros(SAMPLE_RATE)])
    out = process_audio(x, SAMPLE_RATE)
    assert abs(len(out) - round(0.6 * SAMPLE_RATE)) < 5


def test_silent_audio_rejected():
    with pytest.raises(ValueError):
        process_audio(np.zeros(SAMPLE_RATE, dtype=np.float32), SAMPLE_RATE)
    with pytest.raises(ValueError):
        process_audio(np.array([], dtype=np.float32), SAMPLE_RATE)


def test_wav_round_trip_and_bad_cache_rejected(tmp_path):
    p = tmp_path / "a.wav"
    write_wav(p, tone(0.25))
    assert len(read_clip(p)) == round(0.25 * SAMPLE_RATE)
    bad = tmp_path / "bad.wav"
    sf.write(bad, tone(0.25, 16000), 16000, subtype="PCM_16")
    with pytest.raises(ValueError):
        read_clip(bad)
    silent = tmp_path / "silent.wav"
    write_wav(silent, np.zeros(2400, dtype=np.float32))
    with pytest.raises(ValueError):
        read_clip(silent)


# ---- cache keys ----
def test_audio_key_deterministic_and_sensitive():
    base = ("Hello.", "en", "kokoro", "hf_alpha", 1.0, 1.0, "v1")
    assert audio_key(*base) == audio_key(*base)
    variants = [("Hello!",) + base[1:], base[:3] + ("hf_beta",) + base[4:], base[:4] + (1.1,) + base[5:],
                base[:5] + (1.05,) + base[6:], base[:6] + ("v2",)]
    keys = {audio_key(*base)} | {audio_key(*v) for v in variants}
    assert len(keys) == 6


def test_cache_paths_validated(tmp_path):
    c = Cache(tmp_path)
    assert c.lesson_dir("fallback-python-loop", "en-female-1").is_relative_to(c.root)
    assert c.lesson_dir("0123456789ab", "hi-male-1.1").is_relative_to(c.root)
    for bad in ("../x", "fallback-python-loop/../..", "FALLBACK", "fallback-python-loop2", "", "0123456789ab/../.."):
        with pytest.raises(ValueError):
            c.lesson_dir(bad)
    for bad in ("en-female-1/../..", "..", "xx-female-1", "en-other-1", "en-female-"):
        with pytest.raises(ValueError):
            c.lesson_dir("fallback-python-loop", bad)


# ---- timeline ----
def test_schedule_uses_audio_durations(lesson, tmp_path):
    ctx = ctx_for(lesson)
    short = schedule(ctx, fake_clips(lesson, tmp_path, 1.0))
    long = schedule(ctx, fake_clips(lesson, tmp_path, 3.0))
    scenes, starts, total = long
    assert total > short[2]  # duration follows audio, not a constant
    assert scenes[0].start_frame == 0
    for a, b in zip(scenes, scenes[1:]):
        assert b.start_frame == a.start_frame + a.duration_frames
    first = scenes[0].beats[0]
    assert starts[first.beat_id] == LEAD_IN
    assert first.end_frame - first.start_frame == round(3.0 * 30)


def test_title_minimum_and_gaps(lesson, tmp_path):
    ctx = ctx_for(lesson)
    scenes, starts, _ = schedule(ctx, fake_clips(lesson, tmp_path, 0.2))
    title = next(s for s in scenes if s.type == "title_card")
    assert title.duration_frames >= round(TITLE_MIN * 30 / SAMPLE_RATE) - 1
    scene = next(s for s in scenes if len(s.beats) > 1)
    a, b = scene.beats[0], scene.beats[1]
    assert starts[b.beat_id] - starts[a.beat_id] == round(0.2 * SAMPLE_RATE) + BEAT_GAP
    assert SCENE_TAIL > 0


def test_missing_clips_error(lesson):
    with pytest.raises(ValueError):
        schedule(ctx_for(lesson), [])


def test_captions_cover_beat_exactly():
    text = "First sentence is here. Second sentence follows, with a comma and enough words to force a split somewhere."
    caps = build_captions(text, "en", 100, 400)
    assert caps[0].start_frame == 100 and caps[-1].end_frame == 400
    assert all(a.end_frame == b.start_frame for a, b in zip(caps, caps[1:]))
    assert all(len(c.text) <= 90 for c in caps)
    assert " ".join(c.text for c in caps) == text


def test_captions_edge_cases():
    assert chunks("short", "en") == ["short"]
    with pytest.raises(ValueError):
        chunks("   ", "en")
    with pytest.raises(ValueError):
        build_captions("x " * 100, "en", 0, 1)


# ---- SRT ----
def test_srt_timestamp_format():
    assert timestamp(0, 30) == "00:00:00,000"
    assert timestamp(45, 30) == "00:00:01,500"
    assert timestamp(30 * 3661, 30) == "01:01:01,000"


def test_srt_from_timeline(lesson, tmp_path):
    ctx = ctx_for(lesson)
    scenes, _, _ = schedule(ctx, fake_clips(lesson, tmp_path))
    tl = Timeline(lesson_id=lesson.lesson_id, language="en", variant="en-female-1",
                  duration_frames=sum(s.duration_frames for s in scenes), audio=None,
                  voice={"engine": "kokoro", "voice_id": "hf_alpha", "speed": 1.0}, scenes=scenes)
    RenderProps(lesson=lesson, timeline=tl)
    srt = render_srt(tl)
    blocks = [b.splitlines() for b in srt.strip().split("\n\n")]
    assert [b[0] for b in blocks] == [str(i + 1) for i in range(len(blocks))]
    last = -1.0
    for b in blocks:
        start, end = (sum(float(x) * m for x, m in zip(t.replace(",", ".").split(":"), (3600, 60, 1)))
                      for t in b[1].split(" --> "))
        assert start < end and start >= last
        last = start


# ---- timeline schema ----
def test_timeline_schema_rejects_bad_data(lesson, tmp_path):
    scenes, _, _ = schedule(ctx_for(lesson), fake_clips(lesson, tmp_path))
    kw = dict(lesson_id=lesson.lesson_id, language="en", variant="en-female-1", audio=None,
              voice={"engine": "kokoro", "voice_id": "hf_alpha", "speed": 1.0})
    total = sum(s.duration_frames for s in scenes)
    Timeline(duration_frames=total, scenes=scenes, **kw)
    with pytest.raises(ValueError):
        Timeline(duration_frames=total + 1, scenes=scenes, **kw)
    with pytest.raises(ValueError):
        Timeline(duration_frames=total, scenes=scenes, tempo=1.5, **kw)
    with pytest.raises(ValueError):
        Beat(beat_id="a.intro", start_frame=0, end_frame=10,
             captions=[{"text": "x", "start_frame": 0, "end_frame": 11}])


# ---- invalid lesson ----
def test_invalid_lesson_rejected():
    data = json.loads(FALLBACK.read_text(encoding="utf-8"))
    data["scenes"] = []
    with pytest.raises(ValueError):
        Lesson.model_validate(data)
    with pytest.raises(ValueError):
        Lesson.model_validate_json("not json")


# ---- generated artifacts (present after generate_narration; skipped otherwise) ----
OUT = ROOT / "cache" / "lessons" / "fallback-python-loop" / "en-female-1"


@pytest.mark.skipif(not (OUT / "timeline.json").is_file(), reason="run python -m backend.generate_narration first")
def test_generated_artifacts_consistent(lesson):
    tl = Timeline.model_validate_json((OUT / "timeline.json").read_text(encoding="utf-8"))
    RenderProps(lesson=lesson, timeline=tl)
    with wave.open(str(OUT / "narration.wav")) as w:
        wav_seconds = w.getnframes() / w.getframerate()
    assert abs(wav_seconds - tl.duration_frames / tl.fps) < 1 / tl.fps
    assert read_clip(OUT / "narration.wav").size
    assert (OUT / "narration.m4a").stat().st_size > 0
    assert (OUT / "lesson.srt").read_text(encoding="utf-8") == render_srt(tl)
