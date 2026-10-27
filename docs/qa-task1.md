> Gate 1 consolidation update (2026-10-27): this suite has now run against
> the transferred backend in this checkout. The complete backend suite passed
> with 76 passed and 2 skips; see [gate1-validation.md](gate1-validation.md).
> The unchecked checklist and stub-only statement below describe the original QA plan.

# QA — Task 1: FastAPI backend foundation

Test file: `backend/tests/test_task1_qa.py` (25 tests). Run from the repo root with the venv active:
```
python -m pytest backend/tests/test_task1_qa.py -q
```
**Contract** tests check what the docs fix (a failure means the code is wrong). **Assumption** tests depend on Python names the docs don't fix; they skip until mapped in the file's `ADAPTER` dict.
The test code was checked against a throwaway stub written to our docs (23 passed). It has **not** been run against Codex's code.

## 1. Checklist
- [ ] App imports; `/api/health`, `/api/config` and the `/media` mount are registered
- [ ] `/api/health` matches `api-contracts.md` §1, `ok` follows its rule, `device_profile` follows `DEVICE`
- [ ] `/api/config` matches §2 exactly (7 languages, tiers, native names in script, limits, defaults)
- [ ] No paths, model files or secrets in any response
- [ ] `config.py` sets `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE`; `CACHE_DIR` and `DEVICE` come from env
- [ ] `/media` serves files from `CACHE_DIR/lessons`, 404s missing ones, blocks `..`
- [ ] Stage names, job and stage statuses as documented; `runs.jsonl` lines have the 7 keys
- [ ] Cache: topic normalization, 12-hex `lesson_id`, `variant` = `hi-female-1`
- [ ] Python 3.11, transformers 4.46.1, no cloud-AI packages, no external URLs in code, `.gitignore` covers secrets

## 2. Test cases
| ID | Pri | Test | Source |
|---|---|---|---|
| python_is_311 | P0 | Runs on Python 3.11 | README, AGENTS |
| app_imports_and_routes | P0 | Health, config, `/media` registered | architecture §8 |
| health_contract | P0 | All fields and types; `device_profile=cpu`; `offline=true`; `ok` rule | api-contracts §1 |
| health_planner_name_matches_profile | P0 | CPU profile → `PLANNER_MODEL_CPU` | architecture §6 |
| config_contract | P0 | Exact §2 structure and values; हिन्दी, ಕನ್ನಡ, தமிழ் | api-contracts §2 |
| config_exposes_no_paths_or_secrets | P0 | No `C:\`, `MODELS_DIR`, `.onnx`, `.env`, keys | task brief, AGENTS rule 1 |
| config_sets_offline_env | P0 | Importing `config.py` sets both offline vars | architecture §6 |
| media_serves_existing_file | P0 | UTF-8 file under `CACHE_DIR/lessons` → 200 | api-contracts §9 |
| media_missing_file_is_404 | P0 | Missing → 404 | api-contracts §9 |
| media_blocks_path_traversal | P0 | `..`, `%2e%2e`, `..%2f` never 200 | security |
| no_external_urls_in_backend_code | P0 | Only localhost URLs in `backend/` | AGENTS rule 1 |
| no_cloud_ai_packages | P0 | requirements has no OpenAI/Gemini/ElevenLabs/… | PS rules |
| transformers_still_pinned | P0 | 4.46.1 | AGENTS |
| gitignore_covers_secrets_and_generated | P0 | `.env`, `cache`, `models`, `node_modules` | AGENTS |
| health_fast_when_ollama_down | P1 | < 3 s with Ollama unreachable | robustness |
| auto_device_gives_valid_profile | P1 | `DEVICE=auto` → `gpu` or `cpu` | architecture §5 |
| invalid_device_is_handled | P1 | Clear error naming DEVICE, or a valid fallback | task brief |
| config_defaults_are_consistent | P1 | Defaults are inside the lists/ranges | api-contracts §2 |
| unknown_job_is_404 | P1 | Skips if the route isn't built yet | api-contracts §4 |
| stage_names_match_pipeline | P1 · A | `plan…export` in order | pipeline §0 |
| job_and_stage_statuses | P1 · A | Exact status sets | api-contracts §4 |
| topic_normalization | P1 · A | Lowercase, no punctuation, single spaces | pipeline §1 |
| lesson_id_is_stable_12_hex | P1 · A | Deterministic; changes with level, length, model | pipeline §8 |
| variant_name | P1 · A | `hi-female-1`; `kn-male-1.15` | pipeline §8 |
| runs_jsonl_line | P1 · A | Appends a line with the 7 keys | AGENTS |
A = assumption test (skips until mapped).

## 3. Assumptions Codex must check
1. **Config is read at import time from env vars**, and `CACHE_DIR` / `DEVICE` / `OLLAMA_URL` env vars override `.env`. The tests set env vars, then re-import `backend.app.*`. If settings are cached elsewhere (e.g. `lru_cache`), clear that cache in the tests' `_load_app`.
2. **`/media` is a `StaticFiles` mount on `CACHE_DIR/lessons`.** If it serves `CACHE_DIR` instead, the media test paths need a `lessons/` prefix.
3. **`DEVICE=cpu` → `device_profile = "cpu"`** without importing torch. If health imports torch, it still passes, just slower.
4. **`/api/health` doesn't block on Ollama.** Task 1 marks models not ready; later pings need a short timeout.
5. **ADAPTER names:** map the real constant/function names for stages, statuses, `normalize_topic`, `lesson_id(topic, level, target_seconds, model)`, `variant_id(lang, voice, speed)`, and the `runs.jsonl` logger `(record: dict)`. If a signature differs, adjust only the call in that test.
6. **`variant` for non-integer speeds** (`kn-male-1.15`) is our assumption (`{speed:g}`); the docs only show `hi-female-1`.
7. **The planner name test** expects the CPU default `qwen3:4b-instruct-2507-q4_K_M` unless `PLANNER_MODEL_CPU` is set in the environment.

## 4. Prompt for Codex
```
Read AGENTS.md and docs/qa-task1.md. Add backend/tests/test_task1_qa.py (QA tests for Task 1) and run:
  python -m pytest backend/tests -q
1. Map the ADAPTER dict at the top of the test file to the real names in backend/app (jobs.py, cache.py,
   contracts.py). Don't rename production code just to fit the tests.
2. Check the assumptions in docs/qa-task1.md §3. If one doesn't hold, adjust only the test helper or the call,
   and say what you changed.
3. Contract tests (marked by their doc source) must not be weakened. If one fails, fix the backend code to
   match docs/api-contracts.md / docs/architecture.md, not the test.
4. Re-run until no test fails. Skips are OK only for: transformers not installed, /api/jobs not built yet.
5. Report: passed / failed / skipped counts, every code fix, every test adjustment, and anything still
   failing with the reason. Don't touch web/, data/ or install/upgrade packages. Stop after this.
```
