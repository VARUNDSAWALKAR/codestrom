"""Faststart remux and the ffprobe acceptance check (export.md §4, no shell)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from uuid import uuid4

DURATION_TOLERANCE = 0.2


class ExportError(RuntimeError):
    pass


def _run(arguments: list[str], timeout: int = 120) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(arguments, capture_output=True, check=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()[-500:]
        raise ExportError(f"{Path(arguments[0]).name} failed (exit {exc.returncode}): {detail}") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise ExportError(f"Cannot run {arguments[0]}: {exc}") from exc


def faststart(raw: Path, output: Path, ffmpeg: str) -> None:
    """ffmpeg -y -i raw.mp4 -c copy -movflags +faststart lesson.mp4 (via a temp file)."""
    temporary = output.with_name(f".{output.stem}.{uuid4().hex}.mp4")
    try:
        _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-c", "copy",
              "-movflags", "+faststart", str(temporary)])
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def probe(path: Path, ffprobe: str) -> dict:
    result = _run([ffprobe, "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,pix_fmt",
                   "-show_entries", "format=duration", "-of", "json", str(path)])
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise ExportError(f"ffprobe returned invalid JSON for {path.name}") from exc


def validate_mp4(path: Path, expected_seconds: float, ffprobe: str) -> float:
    """Return the probed duration, or raise ExportError naming the failed requirement."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ExportError(f"{path.name} is missing or empty")
    info = probe(path, ffprobe)
    streams = info.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if len(video) != 1:
        raise ExportError(f"Expected exactly one video stream, found {len(video)}")
    v = video[0]
    if v.get("codec_name") != "h264":
        raise ExportError(f"Video codec is {v.get('codec_name')}, expected h264")
    if (v.get("width"), v.get("height")) != (1280, 720):
        raise ExportError(f"Video is {v.get('width')}x{v.get('height')}, expected 1280x720")
    if v.get("pix_fmt") != "yuv420p":
        raise ExportError(f"Pixel format is {v.get('pix_fmt')}, expected yuv420p")
    if len(audio) != 1 or audio[0].get("codec_name") != "aac":
        raise ExportError("Expected exactly one AAC audio stream")
    try:
        duration = float(info["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ExportError("ffprobe did not report a duration") from exc
    if abs(duration - expected_seconds) > DURATION_TOLERANCE:
        raise ExportError(f"Duration {duration:.3f}s differs from timeline {expected_seconds:.3f}s by more than "
                          f"{DURATION_TOLERANCE}s")
    return duration
