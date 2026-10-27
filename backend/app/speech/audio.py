"""Local PCM processing and FFmpeg audio operations (never model-written code)."""
from __future__ import annotations

import io
import subprocess
from pathlib import Path
from uuid import uuid4

import numpy as np
import soundfile as sf

SAMPLE_RATE = 24000
PEAK_LIMIT = 10 ** (-1 / 20)


def ffmpeg_run(executable: str, arguments: list[str], data: bytes | None = None) -> bytes:
    try:
        result = subprocess.run([executable, "-hide_banner", "-loglevel", "error", *arguments],
                                input=data, capture_output=True, check=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, "stderr", b"") or b""
        raise RuntimeError(f"Local FFmpeg audio operation failed: {exc}; {detail.decode('utf-8', errors='replace')}") from exc
    return result.stdout


def process_audio(samples: np.ndarray, rate: int, ffmpeg: str = "ffmpeg") -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    if samples.ndim != 1 or not samples.size or rate <= 0 or not np.isfinite(samples).all():
        raise ValueError("Invalid synthesized audio")
    if rate != SAMPLE_RATE:
        # FFmpeg's anti-aliasing resampler, not naive interpolation.
        raw = ffmpeg_run(ffmpeg, ["-f", "f32le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
                                 "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1", "pipe:1"], samples.astype('<f4').tobytes())
        samples = np.frombuffer(raw, dtype='<f4').copy()
    active = np.flatnonzero(np.abs(samples) >= 0.01)  # -40 dBFS
    if not active.size:
        raise ValueError("Synthesized audio is silent or below -40 dBFS")
    padding = round(0.05 * SAMPLE_RATE)
    samples = samples[max(0, active[0] - padding):min(len(samples), active[-1] + 1 + padding)]
    rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
    gain = min(0.1 / rms, PEAK_LIMIT / float(np.abs(samples).max()))
    return (samples * gain).astype(np.float32)


def write_wav(path: Path, samples: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{uuid4().hex}.wav")
    try:
        sf.write(temporary, samples, SAMPLE_RATE, subtype="PCM_16")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_clip(path: Path) -> np.ndarray:
    info = sf.info(path)
    samples, rate = sf.read(path, dtype="float32")
    if rate != SAMPLE_RATE or info.channels != 1 or info.subtype != "PCM_16":
        raise ValueError(f"Invalid cached PCM format: {path}")
    if not samples.size or not np.isfinite(samples).all() or np.max(np.abs(samples)) < 0.001:
        raise ValueError(f"Silent or invalid cached clip: {path}")
    return samples


def encode_m4a(wav: Path, output: Path, ffmpeg: str) -> None:
    temporary = output.with_name(f".{output.stem}.{uuid4().hex}.m4a")
    try:
        ffmpeg_run(ffmpeg, ["-y", "-i", str(wav), "-c:a", "aac", "-b:a", "64k", "-ac", "1", str(temporary)])
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def change_tempo(source: Path, output: Path, tempo: float, ffmpeg: str) -> None:
    raw = ffmpeg_run(ffmpeg, ["-i", str(source), "-af", f"atempo={tempo:.12g}",
                             "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "wav", "pipe:1"])
    samples, rate = sf.read(io.BytesIO(raw), dtype="float32")
    if rate != SAMPLE_RATE or not np.isfinite(samples).all() or not samples.size:
        raise ValueError("Invalid tempo-adjusted clip")
    peak = float(np.max(np.abs(samples)))
    if peak > PEAK_LIMIT:
        samples *= PEAK_LIMIT / peak
    write_wav(output, samples)
