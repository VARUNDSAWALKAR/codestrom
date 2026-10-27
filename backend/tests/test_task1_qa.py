"""Task 1 QA tests: FastAPI backend foundation (Blu VisualTeacher).

Contract sources:
  docs/api-contracts.md   §1 health, §2 config, §9 media
  docs/architecture.md    §5 device profiles, §6 .env, §8 API
  docs/pipeline.md        §8 cache keys, §0 stages
  AGENTS.md               hard rules, backend rules (runs.jsonl), stack pins

Two kinds of tests:
  CONTRACT    documented in the docs. A failure means the implementation is wrong.
  ASSUMPTION  depends on Python names the docs don't fix (function/constant names).
              Real names are mapped in ADAPTER; missing mappings fail.

Run from the repo root:  python -m pytest backend/tests/test_task1_qa.py -q
"""
from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import pathlib
import re
import sys
import time
import socket
from functools import partial
from typing import Literal, get_args, get_origin

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]

# --- Documented values -------------------------------------------------------
STAGES = ["plan", "validate", "translate", "voice", "timeline", "export"]   # pipeline.md §0
JOB_STATUSES = {"queued", "running", "done", "error"}                          # api-contracts.md §4
STAGE_STATUSES = {"pending", "running", "done", "cached", "skipped", "error"}  # api-contracts.md §4
LANGS_CORE = {"en", "hi", "kn"}
LANGS_BONUS = {"ta", "te", "bn", "mr"}
RUN_LOG_KEYS = {"job_id", "stage", "ms", "rss_mb", "device", "ok", "note"}     # AGENTS.md

# --- ADAPTER: Codex, map these to the real names in backend/app -------------
ADAPTER = {
    "stage_names": ["STAGES"],                    # backend.app.jobs
    "job_statuses": ["JobRecord"],                # status field's Literal
    "stage_statuses": ["StageStatus"],            # Literal type
    "normalize_topic": ["normalize_topic"],      # backend.app.cache
    "lesson_id": ["plan_key"],                    # also requires prompt/schema versions
    "variant_id": ["variant_key"],                # backend.app.cache
    "run_logger": ["Cache.append_run"],           # bound method taking RunRecord
    "cache": ["Cache"],
    "run_record": ["RunRecord"],                  # backend.app.jobs
}


# --- Helpers -----------------------------------------------------------------
def _purge_app_modules(monkeypatch):
    for name in [m for m in list(sys.modules) if m == "backend.app" or m.startswith("backend.app.")]:
        monkeypatch.delitem(sys.modules, name)


def _set_env(monkeypatch, tmp_path, **overrides):
    cache = tmp_path / "cache"
    (cache / "lessons").mkdir(parents=True, exist_ok=True)
    env = {
        "CACHE_DIR": str(cache),
        "DEVICE": "cpu",
        "OLLAMA_URL": "http://127.0.0.1:11434",  # permitted endpoint; failure simulated below
        "PLANNER_MODEL_CPU": os.environ.get("PLANNER_MODEL_CPU", "qwen3:4b-instruct-2507-q4_K_M"),
        "DEFAULT_LANGUAGE": "en",
        "DEFAULT_TARGET_SECONDS": "60",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    env.update(overrides)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    return cache


def _load_app(monkeypatch, tmp_path, **overrides):
    cache = _set_env(monkeypatch, tmp_path, **overrides)
    _purge_app_modules(monkeypatch)
    main = importlib.import_module("backend.app.main")
    return main.app, cache


@pytest.fixture
def client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    app, cache = _load_app(monkeypatch, tmp_path)
    with TestClient(app) as c:
        c.cache_dir = cache
        yield c


def _attr(module_names, key):
    for mod_name in module_names:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for name in ADAPTER[key]:
            obj = mod
            for part in name.split("."):
                if not hasattr(obj, part):
                    break
                obj = getattr(obj, part)
            else:
                return obj
    pytest.fail(f"ADAPTER mapping {ADAPTER[key]} missing in {module_names}")


def _values(obj):
    """Accept real Literal statuses, a model's status field, or collections."""
    if hasattr(obj, "model_fields"):
        obj = obj.model_fields["status"].annotation
    if get_origin(obj) is Literal:
        return list(get_args(obj))
    try:
        return [m.value for m in obj]  # Enum
    except (TypeError, AttributeError):
        return list(obj)


# =============================================================================
# P0 — must pass before Task 2
# =============================================================================

def test_p0_python_is_311():
    assert sys.version_info[:2] == (3, 11), f"Expected Python 3.11 (kavach-env), got {sys.version}"


def test_p0_app_imports_and_routes(monkeypatch, tmp_path):
    app, _ = _load_app(monkeypatch, tmp_path)
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/health" in paths
    assert "/api/config" in paths
    assert any(p == "/media" or p.startswith("/media") for p in paths), "/media is not mounted"


def test_p0_health_contract(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    h = r.json()
    for key in ["ok", "device_profile", "offline", "models", "renderer", "queue_length"]:
        assert key in h, f"missing {key}"
    assert isinstance(h["ok"], bool)
    assert h["device_profile"] == "cpu"            # DEVICE=cpu was set
    assert h["offline"] is True                    # both offline env vars set
    m = h["models"]
    for key in ["planner", "translator", "tts_kokoro", "tts_parler"]:
        assert key in m, f"models.{key} missing"
        assert isinstance(m[key]["ready"], bool)
    assert isinstance(m["planner"]["name"], str)
    assert isinstance(m["translator"]["name"], str)
    assert isinstance(m["tts_parler"]["enabled"], bool)
    assert isinstance(h["renderer"]["bundle_ready"], bool)
    assert isinstance(h["queue_length"], int) and h["queue_length"] >= 0
    # documented rule: ok = planner, translator and Kokoro ready
    assert h["ok"] == (m["planner"]["ready"] and m["translator"]["ready"] and m["tts_kokoro"]["ready"])


def test_p0_health_planner_name_matches_profile(client):
    # architecture.md §6: cpu profile uses PLANNER_MODEL_CPU (default qwen3:4b-instruct-2507-q4_K_M)
    name = client.get("/api/health").json()["models"]["planner"]["name"]
    expected = os.environ.get("PLANNER_MODEL_CPU", "qwen3:4b-instruct-2507-q4_K_M")
    assert name == expected


def test_p0_config_contract(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    c = r.json()
    langs = {l["code"]: l for l in c["languages"]}
    assert set(langs) == LANGS_CORE | LANGS_BONUS
    for code, l in langs.items():
        for key in ["code", "name", "native", "tier", "available"]:
            assert key in l, f"{code}: missing {key}"
        assert l["tier"] == ("core" if code in LANGS_CORE else "bonus"), code
        assert isinstance(l["available"], bool)
    # native names from api-contracts.md §2 (also proves UTF-8 survives)
    assert langs["hi"]["native"] == "हिन्दी"
    assert langs["kn"]["native"] == "ಕನ್ನಡ"
    assert langs["ta"]["native"] == "தமிழ்"
    assert c["levels"] == ["beginner", "intermediate"]
    assert c["target_seconds"] == {"min": 30, "max": 90, "step": 15, "default": 60}
    assert c["voices"] == ["female", "male"]
    assert c["speeds"] == [0.85, 1.0, 1.15]
    assert c["defaults"] == {"language": "en", "level": "beginner", "voice": "female", "speed": 1.0}


def test_p0_config_exposes_no_paths_or_secrets(client):
    text = client.get("/api/config").text + client.get("/api/health").text
    for bad in [":\\\\", "\\\\Users", "/Users/", "MODELS_DIR", "kavach-env", ".onnx", ".env", "API_KEY", "token"]:
        assert bad.lower() not in text.lower(), f"response leaks {bad!r}"


def test_p0_config_sets_offline_env(monkeypatch, tmp_path):
    # architecture.md §6: config.py sets both in os.environ before transformers is imported
    _set_env(monkeypatch, tmp_path, HF_HUB_OFFLINE=None, TRANSFORMERS_OFFLINE=None)
    _purge_app_modules(monkeypatch)
    importlib.import_module("backend.app.config")
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
    assert os.environ.get("TRANSFORMERS_OFFLINE") == "1"


def test_p0_media_serves_existing_file(client):
    folder = client.cache_dir / "lessons" / "abc123def456" / "hi-female-1"
    folder.mkdir(parents=True)
    (folder / "lesson.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nनमस्ते\n", encoding="utf-8")
    r = client.get("/media/abc123def456/hi-female-1/lesson.srt")
    assert r.status_code == 200
    assert "नमस्ते" in r.content.decode("utf-8")


def test_p0_media_missing_file_is_404(client):
    assert client.get("/media/nope/en-female-1/lesson.mp4").status_code == 404


def test_p0_media_blocks_path_traversal(client):
    (client.cache_dir / "secret.txt").write_text("x", encoding="utf-8")
    for url in ["/media/../secret.txt", "/media/%2e%2e/secret.txt", "/media/..%2fsecret.txt"]:
        assert client.get(url).status_code != 200, url


def test_p0_no_external_urls_in_backend_code():
    allowed = re.compile(r"https?://(127\.0\.0\.1|localhost|0\.0\.0\.0)(:\d+)?")
    offenders = []
    for py in (ROOT / "backend").rglob("*.py"):
        if "tests" in py.parts:
            continue
        for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            for url in re.findall(r"https?://[^\s\"')]+", line):
                if not allowed.match(url):
                    offenders.append(f"{py.relative_to(ROOT)}:{n}: {url}")
    assert not offenders, "External URLs (AGENTS.md rule 1):\n" + "\n".join(offenders)


def test_p0_no_cloud_ai_packages():
    req = ROOT / "backend" / "requirements.txt"
    assert req.exists(), "backend/requirements.txt missing (architecture.md §3)"
    banned = ["openai", "anthropic", "google-generativeai", "google-genai", "elevenlabs",
              "google-cloud-translate", "google-cloud-texttospeech", "azure-cognitiveservices", "sarvam"]
    text = req.read_text(encoding="utf-8").lower()
    found = [b for b in banned if re.search(rf"(^|\n)\s*{re.escape(b)}\b", text)]
    assert not found, f"cloud AI packages in requirements: {found}"


def test_p0_transformers_still_pinned():
    try:
        version = importlib.metadata.version("transformers")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("transformers not installed in this env")
    assert version == "4.46.1", f"transformers is {version}; Parler-TTS needs 4.46.1 (never upgrade)"


def test_p0_gitignore_covers_secrets_and_generated():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in [".env", "cache", "models", "node_modules"]:
        assert entry in gi, f".gitignore misses {entry}"


# =============================================================================
# P1 — fix today, doesn't block Task 2
# =============================================================================

def test_p1_health_fast_when_ollama_down(client, monkeypatch):
    def refused(*args, **kwargs):
        raise ConnectionRefusedError("QA: Ollama is unreachable")
    monkeypatch.setattr(socket.socket, "connect", refused)
    start = time.perf_counter()
    assert client.get("/api/health").status_code == 200
    assert time.perf_counter() - start < 3.0, "health must not hang when Ollama is unreachable"


def test_p1_auto_device_gives_valid_profile(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    app, _ = _load_app(monkeypatch, tmp_path, DEVICE="auto")
    with TestClient(app) as c:
        assert c.get("/api/health").json()["device_profile"] in {"gpu", "cpu"}


def test_p1_invalid_device_is_handled(monkeypatch, tmp_path):
    """Either a clear startup error naming DEVICE, or a fallback to a valid profile. Never a silent odd value."""
    from fastapi.testclient import TestClient
    try:
        app, _ = _load_app(monkeypatch, tmp_path, DEVICE="banana")
    except Exception as exc:  # noqa: BLE001
        assert "DEVICE" in str(exc).upper(), f"error doesn't name DEVICE: {exc}"
        return
    with TestClient(app) as c:
        assert c.get("/api/health").json()["device_profile"] in {"gpu", "cpu"}


def test_p1_config_defaults_are_consistent(client):
    c = client.get("/api/config").json()
    codes = {l["code"] for l in c["languages"]}
    d = c["defaults"]
    assert d["language"] in codes and d["level"] in c["levels"]
    assert d["voice"] in c["voices"] and d["speed"] in c["speeds"]
    ts = c["target_seconds"]
    assert ts["min"] <= ts["default"] <= ts["max"]


def test_p1_unknown_job_is_404(client):
    paths = {getattr(r, "path", "") for r in client.app.routes}
    if "/api/jobs/{job_id}" not in paths:
        pytest.skip("GET /api/jobs/{job_id} not built yet (allowed in Task 1)")
    assert client.get("/api/jobs/does-not-exist").status_code == 404


def test_p1_stage_names_match_pipeline(monkeypatch, tmp_path):  # ASSUMPTION (name)
    _set_env(monkeypatch, tmp_path)
    stages = _attr(["backend.app.jobs", "backend.app.contracts"], "stage_names")
    assert _values(stages) == STAGES


def test_p1_job_and_stage_statuses(monkeypatch, tmp_path):  # ASSUMPTION (names)
    _set_env(monkeypatch, tmp_path)
    jobs = _attr(["backend.app.jobs", "backend.app.contracts"], "job_statuses")
    assert set(_values(jobs)) == JOB_STATUSES
    stages = _attr(["backend.app.jobs", "backend.app.contracts"], "stage_statuses")
    assert set(_values(stages)) == STAGE_STATUSES


def test_p1_topic_normalization(monkeypatch, tmp_path):  # ASSUMPTION (name)
    _set_env(monkeypatch, tmp_path)
    norm = _attr(["backend.app.cache"], "normalize_topic")
    # pipeline.md §1: lowercase, punctuation removed, spaces collapsed
    assert norm("  How does a Python LOOP   work?? ") == "how does a python loop work"


def test_p1_lesson_id_is_stable_12_hex(monkeypatch, tmp_path):  # ASSUMPTION (name + signature)
    _set_env(monkeypatch, tmp_path)
    lid = partial(_attr(["backend.app.cache"], "lesson_id"),
                  prompt_version="p1", schema_version="1.0")
    a = lid("How does a loop work?", "beginner", 60, "qwen3:8b")
    assert re.fullmatch(r"[0-9a-f]{12}", a)
    assert a == lid("how does a  loop work", "beginner", 60, "qwen3:8b")    # normalized topic
    assert a != lid("How does a loop work?", "intermediate", 60, "qwen3:8b")
    assert a != lid("How does a loop work?", "beginner", 45, "qwen3:8b")
    assert a != lid("How does a loop work?", "beginner", 60, "qwen3:4b-instruct-2507-q4_K_M")


def test_p1_variant_name(monkeypatch, tmp_path):  # ASSUMPTION (name + signature)
    _set_env(monkeypatch, tmp_path)
    var = _attr(["backend.app.cache"], "variant_id")
    assert var("hi", "female", 1.0) == "hi-female-1"         # documented example
    assert var("kn", "male", 1.15) == "kn-male-1.15"         # assumption: speed formatted with :g


def test_p1_runs_jsonl_line(monkeypatch, tmp_path):  # ASSUMPTION (name + signature)
    cache = _set_env(monkeypatch, tmp_path)
    _purge_app_modules(monkeypatch)
    log = _attr(["backend.app.cache"], "run_logger")
    cache_type = _attr(["backend.app.cache"], "cache")
    record_type = _attr(["backend.app.jobs"], "run_record")
    record = {"job_id": "j_test", "stage": "plan", "ms": 12, "rss_mb": 100.0, "device": "cpu", "ok": True, "note": ""}
    log(cache_type(cache), record_type.model_validate(record))
    line = (cache / "runs.jsonl").read_text(encoding="utf-8").strip().splitlines()[-1]
    assert RUN_LOG_KEYS <= set(json.loads(line))
