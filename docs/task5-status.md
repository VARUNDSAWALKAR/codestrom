# Task 5 status — recovery checkpoint

## Task 5A — done (API + orchestration over injected operations)
Not committed. Baseline: tag `planner-done` (`0893e2d`). The production pipeline is **not** connected; nothing in 5A loads Ollama, a TTS model or the renderer.

### Endpoints (all in `backend/app/lessons_api.py`; contract: `api-contracts.md` §3–5, §11)
| Route | Result |
|---|---|
| `POST /api/lessons` | `202 {job_id, lesson_id, variant, cached, mock}`; `422` `validation_error` / `language_unavailable` / `mock_topic_unavailable`; `429` `busy` (+`Retry-After`); `503` `runner_unavailable` (the 5A `pipeline_unavailable` default was replaced by the production pipeline in 5B) |
| `GET /api/jobs/{job_id}` | `JobRecord` (existing fields plus `preview_ready`, `export_status`, `mock`, `error_detail`); `404 job_not_found` |
| `GET /api/lessons/{lesson_id}?variant=` | lesson + timeline + media + meta, available from preview-ready onward; `404 lesson_not_found` / `preview_not_ready` |

Also: CORS for `localhost:5173`, `127.0.0.1:5173`, `localhost:3000`; `422` bodies use `{"error": {code, message, fields}}`; `GET /api/health` gains `mock_pipeline`. Frontend walkthrough: `frontend-integration.md`.

### Job model changes (`backend/app/jobs.py`, `contracts.py`)
- `JobRecord`: `preview_ready: bool`, `export_status: pending|running|completed|failed|skipped`, `mock: bool`, `error_detail: {stage, code, message} | null`.
- `JobContext.request: LessonRequest | None`; `PipelineError(code, message)` carries a stable error code.
- `JobRunner(..., on_failure="fail")`: a failed stage ends the job as `error` with `error_detail`; no fallback is substituted, later stages stay `pending`, written artifacts are kept. The default `on_failure="fallback"` is unchanged (existing foundation tests pass untouched, apart from one assertion that expected `POST /api/lessons` to be a 404).
- `submit(..., request, mock)`, `update(ctx)` (publish now), `find_active`, `latest`, `add_completed`, `active_count`.

### Orchestrator interface (`backend/app/orchestrator.py`) — what Task 5B implements
```python
@dataclass(frozen=True)
class PipelineOps:
    plan: Operation        # sets run.lesson (English Lesson, lesson_id == run.lesson_id); raise PipelineError(code, msg) on failure
    localize: Operation    # non-English only; sets run.lesson in run.language
    voice: Operation       # synthesise; keep clips in run.data
    timeline: Operation    # persist lesson.json, timeline.json, props.json, lesson.srt (+ narration.m4a/.wav), then run.preview_ready()
    export: Operation      # render lesson.mp4; call run.progress(x)
    validate: Operation = default_validate   # validate_plan(run.lesson, effective_subject)
    precheck: Callable[[LessonRequest], None] | None = None
    mock: bool = False
Operation = Callable[[PipelineRun], None]
```
`PipelineRun` exposes `request`, `lesson`, `lesson_id`, `variant`, `language`, `folder` (the variant cache folder), `settings`, `cache`, `data` (scratch dict), `progress(x)`, `note(text)`, `warn(text)`, `skip(note)`, `preview_ready()`. `create_app(settings, ops)` takes the operations; without `ops` only `MOCK_PIPELINE=1` enables submission.

**Preview callback contract.** `run.preview_ready()` must be called by the timeline operation immediately after the timeline and preview props are persisted. It re-reads and cross-checks the files (`lesson.json`, `timeline.json`, `props.json`, `lesson.srt`; `narration.m4a`/`.wav` when `timeline.audio` is not null; lesson id, variant and language must match the job), writes `meta.json`, sets `preview_ready` and `playable`, and publishes the job at once, so `GET /api/jobs` and `GET /api/lessons` show the preview while export runs. If files are missing or inconsistent it raises `PipelineError("preview_incomplete" | "preview_invalid")` and the job fails at `timeline`. If the operation forgets the call, the wrapper makes it after `timeline` returns; `export` refuses to run without `preview_ready` (`preview_not_ready`). Readiness never comes from the stage alone.

Lesson ids come from `planner.ollama_client.lesson_key(PlanRequest, model)` (the same key `plan_lesson` uses), so the id is known before planning. `cached: true` requires a verified preview **and** a non-empty `lesson.mp4`.

### Mock mode (`MOCK_PIPELINE=1`) — implemented
`backend/app/mock_pipeline.py`, off by default (`Settings.mock_pipeline`). Replays `data/samples/{water_cycle,python_loop,newtons_second_law}.props.json`. Marked `mock: true` on submit/job/lesson, `lesson.model = "mock-pipeline"` (so lesson ids can never collide with real ones), `MOCK:` warnings, startup log warning, `health.mock_pipeline`. Unknown topics → `422 mock_topic_unavailable`. No audio, `export_status: "skipped"`. The sample timelines use `voice.engine: "mock"`, which the backend `Timeline` contract rejects, so a placeholder `kokoro` / `mock-no-audio` voice is substituted. Enable/disable instructions: `frontend-integration.md`.

### Tests (`backend/tests/test_task5a.py`, injected fixture-backed operations, no real TTS/render)
- Focused: **19 passed** (9 subtests): happy path and shapes, non-English translate stage, cached variant, planner / voice / timeline failures (structured error preserved, no fallback, later stages pending), export failure after preview (job `error`, `export_status: failed`, preview artifacts kept, `GET /api/lessons` still 200), preview visible while export runs, callback publishes before the timeline stage ends, readiness requires real files (claimed-but-missing and forgotten callback), inconsistent preview files, 422 field errors, bonus language, 429 busy + dedupe of an active lesson, 404s, variant selection, CORS allow/deny, 503 without a pipeline, mock mode markers / separate ids / no unrelated-topic substitution.
- Full backend suite: **119 passed, 1 skipped** (the skip is `test_task3.py:118`, conditional on `web/render/render.mjs`).

### Not checked in 5A (deferred by instruction)
Ollama availability, the Remotion bundle (`web/build`), the renderer and a built frontend were not required or checked.

## Task 5B — remaining
1. Production `PipelineOps`: `plan` → `plan_lesson` (map `PlanResult.error` to `PipelineError(code, message)`; reuse its cached plan), `validate` (already done inside `plan_lesson`; keep `default_validate` or make it cheap), `localize` → IndicTrans2 with term masking, `voice` → Task 2 stage, `timeline` → `run_timeline` (it writes `props.json`; call `run.preview_ready()` right after), `export` → `run_export` with `run.progress`.
2. Bridge `PipelineRun` to the existing typed contexts (`NarrationContext`, `ExportContext` are `JobContext` subclasses built per stage; `run.data` holds what carries over).
3. `create_app(settings, production_ops())` as the default when `MOCK_PIPELINE` is off; update `health.models.*.ready` from real warm-ups.
4. `GET /api/lessons/{id}` `export_status` is read from in-memory job state when the MP4 is absent (it resets to `pending` after a backend restart); persist it if that matters.
5. Export needs the backend reachable on `127.0.0.1:<port>` (it HEAD-checks the narration WAV); the 5A tests do not exercise this.
6. Later (5C): real acceptance run of the full pipeline on CPU; `POST .../voice`, `PATCH .../scenes`, `GET /api/lessons` library (api-contracts §6–8) are still unimplemented.

---

## Task 5B — in progress (checkpoints)

### Checkpoint 1: preflight (done)
- Task 5A and Task 4 work: **still uncommitted** (tag `task5a` does not exist; only `planner-done`). Nothing committed by me.
- Baseline `test_task5a.py`: 19 passed.
- Ollama reachable at 127.0.0.1:11434; `qwen3:4b-instruct-2507-q4_K_M` listed. Kokoro model + voices present under `C:\Users\ROG\Kavach\models\kokoro\`. `ffmpeg`/`ffprobe` 9.0.2 run. `node` v24.21.0. `web/render/render.mjs` exists. Remotion bundle `web/build/index.html` exists (readiness for 5C still to be exercised).
- **No `.env` file exists**, so `DEVICE=auto` resolves to `gpu` on this machine (CUDA available) and would pick `qwen3:8b`. For the CPU model, run the backend with `DEVICE=cpu` (`$env:DEVICE="cpu"`) or add `DEVICE=cpu` to `.env`. The 5B smoke test sets `device="cpu"` explicitly.

### Checkpoint 2: production ops written (done)
New `backend/app/pipeline_ops.py` (`production_ops()`), wired by `create_app` (selection order: injected `ops` > `MOCK_PIPELINE=1` > production). Also changed: `orchestrator.py` (`PipelineRun.cached()`, `PipelineOps.export_complete`, `Orchestrator.export_verified()` so an MP4 only counts when `props.sha1` matches and ffprobe passes), `lessons_api.py` (`media.mp4` / `export_status` use the verified check), `main.py` (health: `planner.ready` from an Ollama `/api/tags` probe with a 5 s TTL; `tts_kokoro.ready` only after Kokoro really loads; translator stays false), `test_foundation.py` and `test_task5a.py` (the "no pipeline => 503" assertions replaced: the default is now production).

### Checkpoint 3: mocked tests (done)
`backend/tests/test_task5b.py`: 22 passed (13 subtests). Full backend suite: **141 passed, 1 skipped**.

### Checkpoint 4: real smoke test (done, passed)
One real Water Cycle job through FastAPI `TestClient`: real Ollama `qwen3:4b-instruct-2507-q4_K_M` on CPU, real Kokoro, real `run_timeline`; export replaced by a smoke-only op calling `run.skip(...)`. Temporary cache dir, deleted afterwards (verified). Script: scratchpad only, not in the repo.
- Job `done`; `fallback: false`, `mock: false`, `export_status: "skipped"`, `preview_ready` and `playable` true, no `lesson.mp4` and no `props.sha1` (so it cannot be mistaken for a completed export).
- Stage times: plan **31.0 s** (1 attempt, 30.8 s generation), validate 0 ms, translate skipped, voice **13.4 s** (11 beats, 46.1 s of speech, peak 606 MB RSS), timeline **1.8 s** (1524 frames = 50.8 s, tempo 1), export skipped. Wall clock 46.5 s.
- Lesson: topic "Water Cycle", beginner, `en`, source `llm`, 3 scenes (title, flow diagram, flow diagram), 119 narration words, timeline scenes == lesson scenes.
- `GET /api/lessons/{id}` 200: `media.audio_web` (435,134 B), `audio_wav` (2,438,444 B), `srt` (1,244 B), all fetched with 200; `timeline.json` (3,157 B), `props.json` (6,038 B), `lesson.json`, `meta.json` fetched with 200; `mp4: null`. WAV is real speech (24 kHz, 50.8 s, peak 0.64, RMS 0.095), caption text matches the narration.
- Production app (no injected ops) on startup: importing/starting it loads no heavy module (`torch`, `onnxruntime`, `kokoro_onnx` absent); `/api/health` shows `planner.ready: true` from the real Ollama, `tts_kokoro.ready: false`, `translator.ready: false`, `ok: false`.
- In the smoke run itself `/api/health` was not meaningful because ops were injected (no probe, and the Kokoro hook was a local callback).

### Checkpoint 5: final (5B done)
**Files created:** `backend/app/pipeline_ops.py`, `backend/tests/test_task5b.py`. **Modified:** `backend/app/orchestrator.py`, `lessons_api.py`, `main.py`, `backend/tests/test_foundation.py`, `backend/tests/test_task5a.py`, `docs/frontend-integration.md`, `docs/api-contracts.md`, `docs/task5-status.md`. No edits to planner, Kokoro, timeline or exporter internals, `web/`, or shared contracts beyond what 5A added.
**Tests:** `test_task5b.py` 22 passed (13 subtests); full backend suite **141 passed, 1 skipped** (renderer-conditional skip in `test_task3.py`).
**Design notes**
- Lesson id: `Orchestrator.lesson_id_for` and `plan_lesson` both use `lesson_key(PlanRequest, model)`; the smoke test confirmed they agree. A planner lesson with a different id fails the job with `plan_invalid`; ids are never overwritten.
- Kokoro: one `ProductionKokoro` (subclass of the existing engine with a post-load hook) per `production_ops()`; loads on the first uncached beat, reused by all jobs.
- Playable: `run_timeline` sets `playable = True`; the bridge resets it to False and only `run.preview_ready()` (after file verification) sets it True again.
- LOW_RAM (`settings.low_ram`): one `POST /api/chat {"model": planner, "keep_alive": 0}` at the start of the voice operation, i.e. after plan and before TTS; failure -> `LOW_RAM:` warning; no request at all when off.
- Export progress: `run_export` only mutates `job.progress`, so a small pump thread publishes it every 0.5 s through `run.progress`.
- MP4 cache: `Orchestrator.export_verified` (used by POST `cached`, `GET /api/lessons` `media.mp4` and `export_status`) calls `pipeline_ops.export_complete` = valid inputs + `props.sha1` equals the current props fingerprint + ffprobe validation. The result is memoised per (mp4 mtime, size, sha mtime).
- Optional demo-label for the fallback lesson was **skipped** (no fallback lesson is ever served).
- Language message: bonus languages (`ta` etc.) are rejected by the API layer with its own `language_unavailable` message (bonus-language wording); `hi`/`kn` get the required "Hindi/Kannada need translation and voice integration..." text from the production precheck.

**Not verified in 5B (by instruction):** a real Remotion/ffmpeg export, `run_export` through `ExportContext` against the real exporter (only mocked), the `check_media_reachable` HEAD request (needs a real uvicorn), and the concurrent-requests case with the real orchestrator beyond the 5A queue tests.

**Renderer/bundle readiness for 5C:** `web/render/render.mjs` exists, `web/build/index.html` exists, `ffmpeg`/`ffprobe`/`node` run. Not yet exercised.

**Blockers:** none. **Next step (5C):** start the backend with `DEVICE=cpu uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`, POST the Water Cycle request from checkpoint 4 with the real export (do not inject the skip op), confirm `props.sha1`, a probe-valid 1280x720 `lesson.mp4`, `.srt`, `export_status: completed` and `cached: true` on repeat; then test `cached` behaviour after deleting/damaging the MP4. Remaining later work: Hindi/Kannada (translation + voices, Task 6), `POST .../voice`, `PATCH .../scenes`, `GET /api/lessons` library.

---

## Checkpoint 6 — Task 5C acceptance (in progress)

### After Run 1 (Water Cycle) — PASSED (real uvicorn + Ollama cache + Kokoro + Remotion + FFmpeg)
- Env: `DEVICE=cpu`, `MOCK_PIPELINE=0`, `PYTHONUTF8=1`, `LOW_RAM` unset; one uvicorn on `127.0.0.1:8000` (no reload, one worker), model `qwen3:4b-instruct-2507-q4_K_M`, `device_profile: cpu`. Health at start: planner ready, `renderer.bundle_ready: true`, `mock_pipeline: false`, `tts_kokoro.ready: false` (lazy).
- Bundle `C:\Users\ROG\VisualTeacher-varun\web\build\index.html`, modified `2026-10-27T15:48:01+05:30` (IST), 8641 bytes.
- Job `j_5804e58d3ff6`, lesson `c1f63f0ed69b`, variant `en-female-1`, POST 202 in 31 ms, `cached: false`, `mock: false`. Stages: plan **cached** (planner cache hit from the Task 4b CLI run; acceptable per spec), validate 0 ms, translate skipped, voice 10.9 s (11 beats, 45.5 s speech), timeline 1.4 s (1507 frames), export **114.5 s**. Wall clock **127.2 s**. `done`, `export_status: completed`, `fallback: false`, `error: null`.
- **Preview before MP4 observed for real:** first `preview_ready: true` poll at t=12.7 s with `playable: true`, `export_status: running`, timeline `done`, `media.mp4: null`; `GET /api/lessons/...` returned 200 and `audio_web` (428,774 B), `audio_wav` (2,411,244 B), `srt` (1,228 B), `timeline.json`, `props.json` all returned 200 non-empty. The MP4 appeared ~114 s later.
- Memory (psutil, 0.5 s sampling, **sampled** peaks during the 114.6 s export, 220 samples): backend (uvicorn pid 56432) **617.1 MB**; renderer descendants (`node.exe` + `chrome.exe`) **814.7 MB**; backend + renderer **1431.7 MB**; backend + all descendants **1894.8 MB**. Job-stage `rss_mb` (backend only): voice 616.5, timeline 621.2, export 617.1 (plan/validate 71 before Kokoro loaded).
- MP4 `cache\lessons\c1f63f0ed69b\en-female-1\lesson.mp4`, **1,398,933 bytes**; served at `/media/c1f63f0ed69b/en-female-1/lesson.mp4` (200, `video/mp4`). `props.sha1` equals the current props fingerprint. ffprobe: H.264 High, 1280x720, `yuv420p`, 30.0 fps, 1507 frames; AAC 48 kHz stereo; video 50.233 s, audio 50.240 s, container 50.240 s vs timeline 50.2333 s (|diff| video 0.000 s, container 0.007 s, audio-video 0.007 s). Faststart: top-level atoms `ftyp, moov, free, mdat`. Final-MP4 audio `volumedetect`: mean -23.4 dB, max -7.0 dB (non-silent). Duration/volume checks do not prove perceptual A/V sync.
- SRT: 14 cues == 14 timeline captions, ordered, every interval equals the timeline frames; last cue ends 0.6 s before the video end (the designed scene-tail silence).
- Visual: `scratch\accept\water_cycle\contact_sheet.png` + `frame_01..08.png`. Title card, left-to-right flow diagrams with arrows, active step highlighted, captions fit (2 lines at most), no clipping. **Content-quality defect (planner output, not the renderer):** scene s2 is headed "Title Card" and s2/s3 show the same four steps. The lesson passed validation; fixing it is a planner-prompt/validator task, not 5C.
- **Repeat request:** POST 202 in **47 ms**, `cached: true`, same ids, job `done` with all six stages `cached`, `export_status: completed`, MP4 200; `cache/runs.jsonl` line count, MP4 and `props.sha1` mtimes unchanged, uvicorn had no child process. (Job `j_4a2d96e51b93`.)
- **Defect found (damaged-output check):** a copy of the folder with a truncated `lesson.mp4` was still accepted by `export_complete` / the exporter's `validate_mp4`: a faststart MP4 keeps `moov` first, so ffprobe still reports the full duration. A corrupted `props.sha1` was rejected. Fix in the integration layer (exporter internals untouched): `pipeline_ops.mp4_structure_complete()` (top-level boxes must tile the file exactly and contain `moov` + `mdat`) is now part of `export_complete`; and the production `export` op removes `props.sha1` when an existing `lesson.mp4` fails verification (otherwise the exporter's own "fingerprint matches + ffprobe ok" cache path would keep a truncated file) and adds a warning. 2 new regression tests (`Mp4StructureTests`); `test_task5b.py` now 24 passed. Re-check on temp copies: real folder True, truncated False, bad sha False, untouched copy True; real files unchanged. The underlying gap (`export/ffmpeg.py::validate_mp4` accepts truncated faststart files) is **reported, not changed** (exporter internals need authorization).

### Final — Task 5C acceptance (complete; not committed)
**Verified end to end (real HTTP server):** POST -> job polling -> Ollama planner cache hit -> Kokoro narration -> timeline -> early preview -> Remotion/FFmpeg MP4 -> HTTP media (Range works). Two real MP4s: Water Cycle (job `j_5804e58d3ff6`, lesson `c1f63f0ed69b`, 127.2 s wall, 1,398,933 B) and Binary Search (job `j_5c36adf4b88d`, lesson `d09d4030959b`, 147.9 s, 1,673,394 B), both `en-female-1`, model `qwen3:4b-instruct-2507-q4_K_M`, profile `cpu`. Preview was observed at 12.7 s / 15.2 s with `export_status: running` and `mp4: null`, ~114 s / ~133 s before the MP4. Repeat request `cached: true` in 47 ms. Details, per-stage times, RSS snapshots, sampled peaks, ffprobe/faststart/volume/SRT results and contact-sheet paths: `docs/test-log.md` section 8. Bundle unchanged between runs (`2026-10-27T15:48:01+05:30`). No retry was needed for either run. Binary Search has a real `code_walkthrough` scene and it was rendered and inspected.

**Code changes in 5C (integration files only; planner/Kokoro/timeline/exporter internals untouched):**
- `backend/app/pipeline_ops.py`: `mp4_structure_complete()` added to `export_complete`; the production `export` op drops `props.sha1` and warns when an existing `lesson.mp4` fails verification, so a damaged MP4 is really re-rendered.
- `backend/app/lessons_api.py`: the bonus-language message no longer suggests `hi`/`kn`.
- `backend/tests/test_task5b.py`: `Mp4StructureTests` (2 tests) + one assertion on the bonus-language message. Suite: **143 passed, 1 skipped**.
- Docs: `frontend-integration.md` (startup, timings, verified/pending), `test-log.md` section 8, this file.

**Defects found and NOT fixed (need authorization or are out of 5C scope):**
1. `backend/app/export/ffmpeg.py::validate_mp4` accepts a truncated faststart MP4 (ffprobe reads the full duration from the leading `moov`). Mitigated in the integration layer only; the exporter's own cached path would still accept such a file if invoked directly. Suggested fix inside the exporter: also require the box structure to be complete.
2. Planner content quality (4B model): a diagram scene headed "Title Card" and duplicate steps across scenes (Water Cycle); code step `lines` off by one (Binary Search). Validation passes because it only range-checks `lines`. Suggested: validator that the step text appears on a highlighted line, and a prompt note on 1-based line numbers.
3. `GET /media/...?download=1` (api-contracts section 9) is not implemented; documented as pending.

**Not tested:** perceptual audio/video sync by ear; fresh (non-cached) Ollama planning through uvicorn (done in 5B via TestClient); concurrent real jobs; `LOW_RAM=1` against a real Ollama; behaviour with the Remotion bundle missing or stale; Hindi/Kannada (Task 6).

**Cleanup:** the uvicorn processes started for 5C were stopped (port 8000 free); no stray node/chrome processes. Persistent cache lessons `c1f63f0ed69b` and `d09d4030959b` kept as demo backups. Acceptance artifacts kept under `scratch/accept/` (Git-ignored): `water_cycle/`, `binary_search/`, run JSONs, console and server logs.

**Next:** user review, then commit. Task 6 (translation + Hindi/Kannada voices) is the remaining production gap.
