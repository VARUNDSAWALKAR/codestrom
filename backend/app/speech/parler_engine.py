"""Local Indic Parler-TTS: lazy CPU/CUDA loading, named speakers and serialized RNG."""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
import gc
import hashlib
from importlib.metadata import version
import json
import random
from pathlib import Path
from threading import RLock
from time import perf_counter

import numpy as np

from ..config import Settings
from ..jobs import PipelineError
from .audio import ffmpeg_run
from .kn_textnorm import KN_NORMALIZATION_VERSION

SPEAKERS = {"female": "Anu", "male": "Suresh"}
GENERATION = {"do_sample": True, "temperature": 1.0, "top_k": 50, "top_p": 1.0,
              "num_beams": 1, "use_cache": True}
SEQUENCE_POLICY = "seed-once-ordered-utterances-v1"
_MODEL_LOCK = RLock()  # also serializes torch RNG across direct instances


@lru_cache(maxsize=4)
def _assets(files: tuple[tuple[str, int, int], ...]) -> str:
    digest = hashlib.sha256()
    for filename, _, _ in files:
        path = Path(filename)
        digest.update(path.name.encode())
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024*1024), b""):
                digest.update(block)
    return digest.hexdigest()


class ParlerEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = self._prompt = self._description = None
        self._version: str | None = None
        self._sequence_active = False
        self._sequence_devices: list[int] = []
        self.last_metrics: dict[str, float | str] = {}

    @property
    def ready(self) -> bool:
        return self._model is not None

    @property
    def engine_version(self) -> str:
        if self._version is None:
            root, desc = self.settings.parler_model, self.settings.parler_description_tokenizer
            paths = [root / name for name in ("config.json", "generation_config.json", "model.safetensors",
                     "tokenizer.json", "tokenizer.model", "tokenizer_config.json", "special_tokens_map.json")]
            paths += [desc / name for name in ("tokenizer.json", "spiece.model", "tokenizer_config.json", "special_tokens_map.json")]
            files = tuple((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in paths)
            spec = {"assets": _assets(files), "parler": version("parler-tts"), "transformers": version("transformers"),
                    "normalization": KN_NORMALIZATION_VERSION, "postprocess": "24k-pcm-v1",
                    "rng": {"Suresh": SEQUENCE_POLICY, "Anu": "fork-per-beat-v1"},
                    "generation": {**GENERATION, "max_new_tokens": self.settings.parler_max_new_tokens},
                    "seed": self.settings.parler_seed, "description": "named-moderate-clear-v1", "speed": "ffmpeg-atempo-v1"}
            self._version = "parler-" + hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        return self._version

    def _load_components(self):
        import torch
        from transformers import AutoTokenizer
        from parler_tts import ParlerTTSForConditionalGeneration
        profile = self.settings.resolve_profile()
        device = "cuda" if profile == "gpu" else "cpu"
        if device == "cpu":
            torch.set_num_threads(self.settings.parler_cpu_threads)
        prompt = AutoTokenizer.from_pretrained(str(self.settings.parler_model), local_files_only=True, trust_remote_code=False)
        description = AutoTokenizer.from_pretrained(str(self.settings.parler_description_tokenizer), local_files_only=True, trust_remote_code=False)
        model = ParlerTTSForConditionalGeneration.from_pretrained(str(self.settings.parler_model), local_files_only=True,
                    use_safetensors=True, torch_dtype=torch.float32 if device == "cpu" else torch.bfloat16).to(device).eval()
        return model, prompt, description

    def load(self) -> None:
        with _MODEL_LOCK:
            if self.ready:
                return
            if not self.settings.enable_parler:
                raise PipelineError("tts_unavailable", "Indic Parler-TTS is disabled in configuration")
            started = perf_counter()
            try:
                model, prompt, description = self._load_components()
                self._prompt, self._description, self._model = prompt, description, model
                self.last_metrics["load_seconds"] = perf_counter()-started
            except Exception as exc:
                raise PipelineError("tts_unavailable", f"Cannot initialize local Kannada TTS: {exc}") from exc

    @contextmanager
    def session(self):
        # A full voice operation may hold this across all beats/cache publication.
        # Release waits here, so it cannot remove a model while another caller uses it.
        with _MODEL_LOCK:
            yield self

    def release(self) -> None:
        with _MODEL_LOCK:
            self._model = self._prompt = self._description = None
            gc.collect()

    @contextmanager
    def utterance_sequence(self, *, load_model: bool = True):
        """Experiment semantics: load first, seed once, then advance across utterances.

        The existing operation lock covers the complete stream. Outer RNG state is
        restored so this profile cannot perturb other jobs or English/Hindi.
        """
        import torch
        with _MODEL_LOCK:
            if self._sequence_active:
                raise RuntimeError("Nested Kannada utterance sequence")
            if load_model:
                self.load()
            devices = [torch.cuda.current_device()] if self.settings.resolve_profile() == "gpu" else []
            python_state, numpy_state = random.getstate(), np.random.get_state()
            with torch.random.fork_rng(devices=devices):
                random.seed(self.settings.parler_seed)
                np.random.seed(self.settings.parler_seed)
                torch.manual_seed(self.settings.parler_seed)
                self._sequence_active, self._sequence_devices = True, devices
                try:
                    yield self
                finally:
                    self._sequence_active, self._sequence_devices = False, []
                    random.setstate(python_state)
                    np.random.set_state(numpy_state)

    def capture_rng(self) -> dict:
        import torch
        if not self._sequence_active:
            raise RuntimeError("RNG snapshot requires active sequence")
        state = np.random.get_state()
        return {"torch": torch.random.get_rng_state().tolist(), "python": list(random.getstate()),
                "numpy": [state[0], state[1].tolist(), int(state[2]), int(state[3]), float(state[4])],
                "cuda": [torch.cuda.get_rng_state(d).tolist() for d in self._sequence_devices]}

    def restore_rng(self, state: dict) -> None:
        """Data-only cache state, never pickle/unpickle or execute artifact content."""
        import torch
        if not self._sequence_active or not isinstance(state, dict) or set(state) != {"torch", "python", "numpy", "cuda"}:
            raise ValueError("Invalid RNG snapshot")
        def tensor(value, size):
            if not isinstance(value, list) or len(value) != size or any(type(v) is not int or not 0 <= v <= 255 for v in value):
                raise ValueError("Invalid tensor RNG snapshot")
            return torch.tensor(value, dtype=torch.uint8)
        cpu = tensor(state['torch'], torch.random.get_rng_state().numel())
        py, numpy, cuda = state['python'], state['numpy'], state['cuda']
        if (not isinstance(py, list) or len(py) != 3 or py[0] != 3 or len(py[1]) != 625
                or not isinstance(numpy, list) or len(numpy) != 5 or numpy[0] != 'MT19937' or len(numpy[1]) != 624
                or not isinstance(cuda, list) or len(cuda) != len(self._sequence_devices)):
            raise ValueError("Invalid host/device RNG snapshot")
        torch.random.set_rng_state(cpu)
        random.setstate((py[0], tuple(py[1]), py[2]))
        np.random.set_state((numpy[0], np.asarray(numpy[1], dtype=np.uint32), numpy[2], numpy[3], numpy[4]))
        for device, value in zip(self._sequence_devices, cuda):
            torch.cuda.set_rng_state(tensor(value, torch.cuda.get_rng_state(device).numel()), device)

    @contextmanager
    def _beat_rng(self, devices):
        import torch
        if self._sequence_active:
            yield
        else:
            with torch.random.fork_rng(devices=devices):
                torch.manual_seed(self.settings.parler_seed)
                yield

    def _generate(self, text: str, speaker: str) -> tuple[np.ndarray, int]:
        import torch
        self.load()
        description = (f"{speaker} speaks with a moderate speed and pitch. The recording is of very high quality, "
                       "with the speaker's voice sounding clear and very close up.")
        device = next(self._model.parameters()).device
        d = self._description(description, return_tensors="pt").to(device)
        p = self._prompt(text, return_tensors="pt").to(device)
        if p.input_ids.shape[-1] > 512:
            raise PipelineError("tts_invalid_text", "Kannada beat exceeds the local prompt context")
        devices = [] if device.type == "cpu" else [device.index or 0]
        with self._beat_rng(devices), torch.inference_mode():
            generated = self._model.generate(input_ids=d.input_ids, attention_mask=d.attention_mask,
                prompt_input_ids=p.input_ids, prompt_attention_mask=p.attention_mask,
                max_new_tokens=self.settings.parler_max_new_tokens, **GENERATION)
        rate = int(self._model.config.sampling_rate)
        raw = generated.detach().cpu().numpy().squeeze().astype(np.float32)
        hop = int(self._model.config.audio_encoder.hop_length)
        if raw.size >= (self.settings.parler_max_new_tokens - 20) * hop:
            raise PipelineError("tts_generation_limit", "Kannada speech approached generation cap; refusing potentially truncated audio")
        return raw, rate

    def synthesize(self, text: str, language: str, voice_id: str, speed: float):
        if language != "kn" or voice_id not in SPEAKERS.values():
            raise PipelineError("voice_unavailable", "Kannada Parler supports named speakers Anu and Suresh only")
        if not 0.8 <= speed <= 1.2:
            raise PipelineError("voice_unavailable", "Voice speed must be between 0.8 and 1.2")
        with _MODEL_LOCK:
            started = perf_counter()
            try:
                raw, rate = self._generate(text, voice_id)
                raw = np.asarray(raw, dtype=np.float32)
                if (raw.ndim != 1 or not raw.size or rate <= 0 or not np.isfinite(raw).all()
                        or np.max(np.abs(raw)) < 0.001 or np.sqrt(np.mean(raw.astype(np.float64)**2)) < 1e-5):
                    raise PipelineError("tts_invalid_audio", "Kannada synthesis returned silent/invalid audio")
                if speed != 1.0:
                    data = ffmpeg_run(self.settings.ffmpeg, ["-f", "f32le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
                        "-af", f"atempo={speed:g}", "-f", "f32le", "-ar", str(rate), "-ac", "1", "pipe:1"], raw.astype('<f4').tobytes())
                    raw = np.frombuffer(data, dtype='<f4').copy()
                self.last_metrics["inference_seconds"] = perf_counter()-started
                self.last_metrics["speaker"] = voice_id
                return raw, rate
            except PipelineError:
                raise
            except Exception as exc:
                raise PipelineError("tts_failed", f"Kannada synthesis failed: {exc}") from exc


_ENGINES: dict[tuple, ParlerEngine] = {}


def _key(settings: Settings) -> tuple:
    return (settings.parler_model, settings.parler_description_tokenizer, settings.device,
            settings.parler_cpu_threads, settings.parler_seed, settings.parler_max_new_tokens)


def get_parler_engine(settings: Settings) -> ParlerEngine:
    with _MODEL_LOCK:
        key = _key(settings)
        if key not in _ENGINES:
            _ENGINES[key] = ParlerEngine(settings)
        return _ENGINES[key]


def parler_ready(settings: Settings) -> bool:
    engine = _ENGINES.get(_key(settings))
    return engine is not None and engine.ready


def release_parler(settings: Settings) -> None:
    with _MODEL_LOCK:
        engine = _ENGINES.get(_key(settings))
        if engine is not None:
            engine.release()
