"""The only environment-reading module. Import before any model libraries."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Enforce these before torch or any future transformers import, even if the
# launching shell mistakenly supplies zero. Offline mode is not optional.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

ROOT = Path(__file__).resolve().parents[2]
Language = Literal["en", "hi", "kn", "ta", "te", "bn", "mr"]
DeviceProfile = Literal["cpu", "gpu"]


def read_env_file(path: Path) -> dict[str, str]:
    """Read the literal KEY=value format in architecture.md (no expansion).

    Quoted values and whole-line comments are supported; backslashes in
    Windows paths remain literal. Shell environment values take precedence.
    """
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key.strip().isidentifier():
            raise ValueError(f"Invalid .env assignment on line {number}")
        value = value.strip()
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"Unclosed .env quote on line {number}")
            value = value[1:-1]
        values[key.strip().upper()] = value
    return values


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ollama_url: str = "http://127.0.0.1:11434"
    planner_model_gpu: str = "qwen3:8b"
    planner_model_cpu: str = "qwen3:4b-instruct-2507-q4_K_M"
    planner_backup_model: str = "llama3.2:3b"
    models_dir: Path = Path("C:/Users/ROG/Kavach/models")
    kokoro_model: Path = Path("kokoro") / "kokoro-v1.0.onnx"
    kokoro_voices: Path = Path("kokoro") / "voices-v1.0.bin"
    kokoro_voice_female: str = "hf_alpha"
    kokoro_voice_male: str = "hm_omega"
    kokoro_english_lang: Literal["en-us", "en-gb"] = "en-us"
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    indictrans_model: Path = Path("indictrans2")
    parler_model: Path = Path("indic-parler-tts")
    enable_parler: bool = True
    device: Literal["auto", "cuda", "cpu"] = "auto"
    low_ram: bool = False
    port: int = Field(default=8000, ge=1, le=65535)
    cache_dir: Path = ROOT / "cache"
    web_dist: Path = ROOT / "web" / "dist"
    render_bundle: Path = ROOT / "web" / "build"
    render_script: Path = ROOT / "web" / "render" / "render.mjs"
    render_concurrency: int = Field(default=0, ge=0)  # 0 = automatic; the export stage uses 2
    render_timeout_seconds: int = Field(default=900, ge=1)
    node_binary: str = "node"
    export_fps: Literal[30] = 30
    default_language: Language = "en"
    default_target_seconds: int = Field(default=60, ge=30, le=90)
    max_queued_jobs: int = Field(default=2, ge=0)  # waiting jobs beyond the running one before POST answers 429
    mock_pipeline: bool = False  # MOCK_PIPELINE=1: development-only fixture pipeline; off by default

    @field_validator("ollama_url")
    @classmethod
    def localhost_only(cls, value: str) -> str:
        url = urlsplit(value)
        if (url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1"}
                or url.port != 11434 or url.username or url.password
                or url.path not in {"", "/"} or url.query or url.fragment):
            raise ValueError("OLLAMA_URL must be the local Ollama service on port 11434")
        return value.rstrip("/")

    @model_validator(mode="after")
    def absolute_paths(self) -> Settings:
        for name in ("models_dir", "cache_dir", "web_dist", "render_bundle", "render_script"):
            path = getattr(self, name)
            object.__setattr__(self, name, (ROOT / path).resolve())
        for name in ("kokoro_model", "kokoro_voices", "indictrans_model", "parler_model"):
            object.__setattr__(self, name, (self.models_dir / getattr(self, name)).resolve())
        return self

    @property
    def offline(self) -> bool:
        return os.environ.get("HF_HUB_OFFLINE") == "1" and os.environ.get("TRANSFORMERS_OFFLINE") == "1"

    def resolve_profile(self) -> DeviceProfile:
        if self.device == "cpu":
            return "cpu"
        try:
            import torch
            available = torch.cuda.is_available()
        except (ImportError, OSError):
            available = False
        if self.device == "cuda" and not available:
            raise ValueError("DEVICE=cuda requested but CUDA is unavailable; use DEVICE=cpu or auto")
        return "gpu" if available else "cpu"

    def planner_model(self, profile: DeviceProfile) -> str:
        return self.planner_model_gpu if profile == "gpu" else self.planner_model_cpu


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    values = read_env_file(ROOT / ".env")
    values.update(os.environ)
    return Settings.model_validate({
        name: values[name.upper()] for name in Settings.model_fields if name.upper() in values
    })
