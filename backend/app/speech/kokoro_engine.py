"""Lazy local Kokoro loader. The documented Kokoro profile is always CPU."""
from __future__ import annotations

import hashlib
from importlib.metadata import version
from threading import Lock

from ..config import Settings


class KokoroEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None
        self._lock = Lock()
        self._version: str | None = None

    @property
    def engine_version(self) -> str:
        if self._version is None:
            digest = hashlib.sha256()
            for path in (self.settings.kokoro_model, self.settings.kokoro_voices):
                if not path.is_file():
                    raise FileNotFoundError(f"Missing local Kokoro asset: {path}")
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
            self._version = f"kokoro-onnx-{version('kokoro-onnx')}-pcm-v1-{self.settings.kokoro_english_lang}-{digest.hexdigest()[:16]}"
        return self._version

    def load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            _ = self.engine_version
            try:
                import onnxruntime as ort
                from kokoro_onnx import Kokoro
                options = ort.SessionOptions()
                options.enable_mem_pattern = not self.settings.low_ram
                session = ort.InferenceSession(str(self.settings.kokoro_model), sess_options=options,
                                               providers=["CPUExecutionProvider"])
                self._model = Kokoro.from_session(session, str(self.settings.kokoro_voices))
            except Exception as exc:
                raise RuntimeError(f"Cannot load local Kokoro on CPU: {exc}") from exc

    def synthesize(self, text: str, language: str, voice_id: str, speed: float):
        if language not in {"en", "hi"}:
            raise ValueError(f"Task 2 Kokoro language not supported: {language}")
        self.load()
        with self._lock:
            try:
                return self._model.create(text, voice=voice_id, speed=speed,
                                          lang=self.settings.kokoro_english_lang if language == "en" else "hi",
                                          trim=False)
            except Exception as exc:
                raise RuntimeError(f"Local Kokoro synthesis failed ({language}, {voice_id}): {exc}") from exc
