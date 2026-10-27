"""Lazy local IndicTrans2 singleton, serialized inference and synchronized release."""
from __future__ import annotations

from functools import lru_cache
import hashlib
from pathlib import Path
from threading import RLock
from typing import Protocol

from ..config import Settings


class Translator(Protocol):
    @property
    def identity(self) -> str: ...
    def translate(self, texts: list[str], target_tag: str, *, num_beams: int) -> list[str]: ...


@lru_cache(maxsize=4)
def _asset_identity(files: tuple[tuple[str, int, int], ...]) -> str:
    digest = hashlib.sha256()
    for filename, _, _ in files:
        path = Path(filename)
        digest.update(path.name.encode())
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return "indictrans2-en-indic-dist-200M:" + digest.hexdigest()


class IndicTranslator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.lock = RLock()
        self.model = self.tokenizer = self.processor = None

    @property
    def identity(self) -> str:
        root = self.settings.indictrans_model
        names = ["config.json", "tokenizer_config.json", "generation_config.json", "special_tokens_map.json",
                 "configuration_indictrans.py", "modeling_indictrans.py", "tokenization_indictrans.py",
                 "model.SRC", "model.TGT", "dict.SRC.json", "dict.TGT.json",
                 "model.safetensors" if (root / "model.safetensors").is_file() else "pytorch_model.bin"]
        files = tuple((str(root / n), (root / n).stat().st_size, (root / n).stat().st_mtime_ns) for n in names)
        return _asset_identity(files)

    def load(self) -> None:
        with self.lock:
            if self.model is not None:
                return
            import torch
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            from IndicTransToolkit import IndicProcessor
            path = str(self.settings.indictrans_model)
            profile = self.settings.resolve_profile()
            device = "cuda" if profile == "gpu" else "cpu"
            if device == "cpu":
                torch.set_num_threads(self.settings.localize_cpu_threads)
            tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True, local_files_only=True)
            model = AutoModelForSeq2SeqLM.from_pretrained(
                path, trust_remote_code=True, local_files_only=True,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32).to(device).eval()
            processor = IndicProcessor(inference=True)
            self.tokenizer, self.processor, self.model = tokenizer, processor, model

    def translate(self, texts: list[str], target_tag: str, *, num_beams: int = 2) -> list[str]:
        if not texts:
            return []
        if len(texts) > 16:
            raise ValueError("Translation batches are limited to 16")
        with self.lock:
            self.load()
            import torch
            batch = self.processor.preprocess_batch(texts, src_lang="eng_Latn", tgt_lang=target_tag)
            # Fail explicitly rather than silently truncating protected content.
            encoded = self.tokenizer(batch, padding=True, truncation=False, return_tensors="pt")
            if encoded.input_ids.shape[1] > 256:
                raise ValueError("Translation input exceeds local model's 256-token context")
            encoded = encoded.to(next(self.model.parameters()).device)
            with torch.inference_mode():
                output = self.model.generate(**encoded, max_length=256, num_beams=num_beams)
            decoded = self.tokenizer.batch_decode(output, skip_special_tokens=True)
            return self.processor.postprocess_batch(decoded, lang=target_tag)

    def release(self) -> None:
        with self.lock:
            self.model = self.tokenizer = self.processor = None


OPERATION_LOCK = RLock()
_instances: dict[tuple[Path, str], IndicTranslator] = {}


def get_translator(settings: Settings) -> IndicTranslator:
    with OPERATION_LOCK:
        key = (settings.indictrans_model, settings.resolve_profile())
        if key not in _instances:
            _instances[key] = IndicTranslator(settings)
        return _instances[key]


def translator_ready(settings: Settings) -> bool:
    # Snapshot reads are atomic in CPython. Health must not wait behind a whole
    # translation transaction; load publishes model only after all assets succeed.
    instance = _instances.get((settings.indictrans_model, settings.resolve_profile()))
    return instance is not None and instance.model is not None


def release_translator(settings: Settings) -> None:
    # Waits for full localization (including disk publication), then for any direct inference.
    with OPERATION_LOCK:
        instance = _instances.get((settings.indictrans_model, settings.resolve_profile()))
        if instance is not None:
            instance.release()
