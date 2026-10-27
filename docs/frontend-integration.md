# Frontend integration — lesson API (Tasks 5A + 5B)

For Varun. Contract of record: [api-contracts.md](api-contracts.md) §3–5 and §11. This page is the practical walkthrough.

> **Status (Task 5B).** `POST /api/lessons` now runs the **real pipeline**: Ollama planner → validation → Kokoro narration → timeline/captions/props → (export). **English only.** Hindi and Kannada need translation and multilingual voice, which are not connected yet (Task 6), so they are rejected with `422 language_unavailable`. The MP4 export is wired but its end-to-end run is verified in Task 5C. A separate, clearly labelled development mock mode exists (end of this page); it is not the default.

## Running the backend
- **Ollama must already be running** with the planner model pulled (`qwen3:4b-instruct-2507-q4_K_M` on CPU). The backend does not start or pull it.
- Choose the CPU profile explicitly: `$env:DEVICE="cpu"` (or `DEVICE=cpu` in `.env`). With `DEVICE=auto` a machine with CUDA picks the GPU model `qwen3:8b`.
- Start: `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
- **Kokoro loads on the first voice request** (not at startup) and is reused afterwards, so the first lesson after a restart is slower. `tts_kokoro.ready` in `/api/health` turns true only after that load succeeds.
- **Real MP4 export needs uvicorn listening on `127.0.0.1:<port>`** (default 8000): the renderer downloads the narration WAV from `http://127.0.0.1:8000/media/...`, and the exporter checks that URL first. It also needs the built Remotion bundle (`cd web && npx remotion bundle`, output `web/build`). The end-to-end MP4 test is Task 5C.
- Optional `LOW_RAM=1`: after planning, the planner model is unloaded from Ollama once per job (`keep_alive: 0`) before TTS starts. A failed unload only adds a job warning beginning `LOW_RAM:`.

Base URL: same origin in the built app; in `npm run dev` Vite proxies `/api` and `/media` to `127.0.0.1:8000`. JSON, `snake_case`.

## Flow
1. `POST /api/lessons` → `202` with a `job_id`.
2. Poll `GET /api/jobs/{job_id}` every 500 ms.
3. As soon as `preview_ready` is `true`, fetch `GET /api/lessons/{lesson_id}?variant=…` and open the player. **Do not wait for the MP4.**
4. Keep polling the job for `export_status` / `progress`; when `export_status` is `completed`, `media.mp4` is available (re-fetch the lesson).
5. Stop polling when `status` is `done` or `error`.

## POST /api/lessons
```json
{"topic": "Water Cycle", "level": "beginner", "language": "hi", "target_seconds": 60, "voice": "female", "speed": 1.0}
```
Only `topic` is required (3–120 characters after trimming). Defaults: `beginner`, `en`, `60`, `female`, `1.0`. Unknown fields are rejected. Optional `subject` (`programming` | `science` | `other`) forces the planner's subject.

`202`:
```json
{"job_id": "j_e108b4fe3d8a", "lesson_id": "81fb5e8d6cef", "variant": "hi-female-1", "cached": false, "mock": false}
```
`cached: true` means the variant is already complete; the job is already `done`. Asking again for a lesson that is still queued or running returns that job's ids.

## GET /api/jobs/{job_id}
```json
{
  "job_id": "j_e108b4fe3d8a", "kind": "create", "status": "running", "queue_position": 0,
  "lesson_id": "81fb5e8d6cef", "variant": "hi-female-1",
  "playable": true, "preview_ready": true, "export_status": "running", "mock": false,
  "fallback": false, "fallback_reason": null, "progress": 0.4,
  "stages": [
    {"name": "plan", "status": "done", "ms": 9120, "rss_mb": 1810, "note": ""},
    {"name": "validate", "status": "done", "ms": 14, "rss_mb": 1810, "note": ""},
    {"name": "translate", "status": "done", "ms": 3300, "rss_mb": 2100, "note": ""},
    {"name": "voice", "status": "done", "ms": 8000, "rss_mb": 2300, "note": ""},
    {"name": "timeline", "status": "done", "ms": 700, "rss_mb": 2300, "note": ""},
    {"name": "export", "status": "running", "ms": null, "rss_mb": null, "note": ""}
  ],
  "warnings": [], "error": null, "error_detail": null, "total_ms": 21000, "device_profile": "cpu"
}
```
- `status`: `queued` → `running` → `done` | `error`. `translate` is `skipped` for English. Stages after a failed one stay `pending`.
- `progress` is the export progress (0–1).
- **`fallback` is never set by these jobs.** A failed stage is reported honestly, with no substitute lesson.

### Production job notes (Task 5B)
- Stage `note` fields are real: plan shows the model, attempts and generation seconds (or `Planner cache hit`); voice shows beat counts and how many were cached; timeline shows frames and tempo.
- Repeating a request that was already exported and verified returns `cached: true` and a job that is `done` with every stage `cached`. A request whose MP4 is missing or fails the exporter's checks (`props.sha1` fingerprint + ffprobe) is not a cache hit; it re-runs, with plan / voice / timeline reported as `cached` and only the export doing work.
- `export_status: "skipped"` is not used by production jobs.

### Failure
```json
{"status": "error", "error": "Narration has 261 words; require 90-180 (aim for 110-130). Remove about 131 words.",
 "error_detail": {"stage": "plan", "code": "validation_failed", "message": "Narration has 261 words; …"},
 "preview_ready": false, "playable": false, "export_status": "pending"}
```
Show `error_detail.message`; use `error_detail.stage` to say where it failed. Codes by stage: **plan**: `validation_failed`, `timeout`, `unavailable`, `ollama_rejected`, `ollama_error`, `unsupported_options`, `planner_error` (all from the planner, unchanged), `plan_invalid` (planner returned a lesson with the wrong id/language); **validate**: `validation_failed`, `plan_invalid`; **voice**: `tts_failed`; **timeline**: `timeline_failed`, `preview_incomplete`, `preview_invalid`; **export**: `export_failed`, `preview_not_ready`. There is never a substitute lesson: a failed planner request is a failed job, not the Python-loop demo.

If **export** fails after the preview was ready, the job is `error` and `export_status` is `failed`, but `preview_ready` and `playable` stay `true` and the lesson is still fully playable in the browser. Show a "video export failed" notice with a retry, not a dead end.

## Preview readiness
`preview_ready: true` is set only after the backend verified the files on disk (`lesson.json`, `timeline.json`, `props.json`, `lesson.srt`, and the narration audio when the timeline has audio). It is not inferred from the stage. It can turn true while the `timeline` stage is still finishing and always before `export` starts.

## GET /api/lessons/{lesson_id}?variant=hi-female-1
Returns `200` as soon as the preview is ready (even while export is running):
```json
{
  "lesson_id": "81fb5e8d6cef", "variant": "hi-female-1",
  "preview_ready": true, "export_status": "running", "mock": false,
  "lesson": { "…": "localized lesson (lesson-schema.md §1)" },
  "timeline": { "…": "timeline (lesson-schema.md §6)" },
  "media": {
    "audio_web": "/media/81fb5e8d6cef/hi-female-1/narration.m4a",
    "audio_wav": "/media/81fb5e8d6cef/hi-female-1/narration.wav",
    "mp4": null,
    "srt": "/media/81fb5e8d6cef/hi-female-1/lesson.srt"
  },
  "meta": {"source": "llm", "model": "qwen3:4b-instruct-2507-q4_K_M", "warnings": [],
           "stage_ms": {"plan": 9120}, "variants": ["hi-female-1"], "job_id": "j_e108b4fe3d8a"}
}
```
- Any `media` entry is `null` when that file does not exist yet (`mp4` until export finishes; `audio_*` when the timeline has `audio: null`, in which case render silently).
- Without `variant` you get the most recent preview-ready variant.
- Render props for the player: `{lesson, timeline, mediaBase: "", audioVariant: "web", showCaptions: true}` (api-contracts §5 / lesson-schema §7).

## Busy and error responses
Every error is `{"error": {"code": "…", "message": "…"}}`.

| Status | `code` | Meaning / what to do |
|---|---|---|
| 422 | `validation_error` | `error.fields` is `[{"field": "topic", "message": "…"}]`; highlight the fields |
| 429 | `busy` | The single worker and its queue are full. Wait `Retry-After` seconds (also `error.retry_after`), then retry. Queue limit is `MAX_QUEUED_JOBS` (default 2 waiting jobs) |
| 422 | `language_unavailable` | Production accepts `en` only (see Languages) |
| 503 | `runner_unavailable` | The worker is shutting down |
| 404 | `job_not_found` / `lesson_not_found` | Unknown id; `preview_not_ready` when the lesson exists but nothing is playable yet |

## Languages
`GET /api/config` lists all seven. **Production (default) accepts `en` only.** `hi` and `kn` (`tier: "core"`) return `422 language_unavailable` with the message *"Hindi/Kannada need translation and voice integration that is not connected yet…"*; the bonus languages `ta`, `te`, `bn`, `mr` return the same code. Nothing is silently relabelled as English. `available` in `/api/config` is `false` for every language (listening-test approval has not been recorded) and is not updated by 5B: **until Task 6, offer only English in the language picker** (you can show Hindi/Kannada disabled). Mock mode (below) is a separate labelled path that does accept `hi`/`kn`.

## Health gating
`GET /api/health` has `ok = planner && translator && tts_kokoro`. Translation is not built, so **`ok` stays `false` until Task 6. Do not gate the UI on `ok`.** Gate on:
- `models.planner.ready`: true only while Ollama answers and lists the planner model (checked at most every 5 s). Disable "Create" when false.
- `models.tts_kokoro.ready`: false until the first voice request has loaded Kokoro, then true. It is **not** a reason to block "Create" (it is false on a fresh start); show it as informational ("voice warms up on first use").
- `models.translator.ready` is always `false` for now.
`mock_pipeline: true` means the fixture pipeline is active; show the MOCK banner.

## CORS
Allowed origins: `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000` (Remotion Studio). Methods `GET`, `POST`, `PATCH`; header `Content-Type`. The built app is same-origin and needs none of this. Nothing else is allowed (AGENTS.md rule 1).

## Development mock mode (optional, never the default)
Lets you build the UI without Ollama or TTS (and is the only mode that accepts `hi`/`kn`, with English text). It replays the repository's sample lessons (`data/samples/*.props.json`); it never calls Ollama, TTS or the renderer.

- **Enable:** set `MOCK_PIPELINE=1` in `.env` (or `$env:MOCK_PIPELINE="1"` in the shell before `uvicorn …`). Restart the backend. The log shows a `MOCK_PIPELINE is enabled` warning and `GET /api/health` returns `"mock_pipeline": true`.
- **Disable:** remove the line (or set `MOCK_PIPELINE=0`) and restart. It is off by default and must be off for acceptance runs.
- **Topics:** only `Water Cycle`, `Python loop` (or `Python for loop`) and `Newton's second law`. Any other topic gets `422 mock_topic_unavailable`; it is never answered with an unrelated sample.
- **Markers:** `mock: true` on the submit response, the job and the lesson response; `lesson.source` is `"sample"`, `lesson.model` is `"mock-pipeline"`, and `meta.warnings` start with `MOCK:`. Show a visible "MOCK DATA" banner whenever `mock` is true.
- **Behaviour:** text is always English (language `hi`/`kn` only changes the label, with a `MOCK:` warning), there is no audio (`audio_* = null`, silent playback), and no MP4 (`export_status: "skipped"`, `media.mp4 = null`).
- Mock lessons get their own lesson ids and can never be served as real cached lessons.
