# API contracts — Blu VisualTeacher

> Task 4 override: see [offline planner contract](planner-task4.md). Planner calls use 180 s, keep_alive 10m, one repair, failure-only raw logs, and English content with requested-language metadata. Failed requests return structured errors; no unrelated fallback. Task 5A (below) adds the lesson/job endpoints; Task 5B connects the production pipeline (English only for now).

Build file · Every endpoint and its JSON. Backend: `backend/app/main.py` (Satwik). Client: `web/src/app/api.ts` (Varun).
**This is a contract: change it only together, in the same commit as the code.**

Conventions: JSON, `snake_case`. Errors: `{"error": {"code": "…", "message": "…"}}` with a 4xx/5xx status. Base URL: same origin (`""`) in the built app; Vite proxies `/api` and `/media` to `:8000` in dev.

---

## 1. `GET /api/health`
Polled by the UI on load and every 10 s.
```json
{
  "ok": true,
  "device_profile": "gpu",
  "offline": true,
  "models": {
    "planner": {"name": "qwen3:8b", "ready": true},
    "translator": {"name": "indictrans2-en-indic-dist-200M", "ready": true},
    "tts_kokoro": {"ready": true},
    "tts_parler": {"ready": true, "enabled": true}
  },
  "renderer": {"bundle_ready": true},
  "queue_length": 0,
  "mock_pipeline": false
}
```
`mock_pipeline` is true only when the development-only `MOCK_PIPELINE=1` is set (Task 5A); show a banner if it is.
`offline` is true when `HF_HUB_OFFLINE` and `TRANSFORMERS_OFFLINE` are set. `ok` = planner, translator and Kokoro ready.

## 2. `GET /api/config`
```json
{
  "languages": [
    {"code": "en", "name": "English", "native": "English", "tier": "core", "available": true},
    {"code": "hi", "name": "Hindi", "native": "हिन्दी", "tier": "core", "available": true},
    {"code": "kn", "name": "Kannada", "native": "ಕನ್ನಡ", "tier": "core", "available": true},
    {"code": "ta", "name": "Tamil", "native": "தமிழ்", "tier": "bonus", "available": false}
  ],
  "levels": ["beginner", "intermediate"],
  "target_seconds": {"min": 30, "max": 90, "step": 15, "default": 60},
  "voices": ["female", "male"],
  "speeds": [0.85, 1.0, 1.15],
  "defaults": {"language": "en", "level": "beginner", "voice": "female", "speed": 1.0}
}
```
`available` depends on the device profile and the listening tests (`narration-languages.md` §1).

## 3. `POST /api/lessons` — make a lesson
Request:
```json
{"topic": "How does a Python loop work?", "level": "beginner", "language": "hi", "target_seconds": 60, "voice": "female", "speed": 1.0}
```
Rules: `topic` 3–120 chars after trimming; enums as in §2; `target_seconds` 30–90; `speed` 0.8–1.2. Every field except `topic` is optional (defaults: `beginner`, `en`, 60, `female`, 1.0). An optional `subject` (`programming` | `science` | `other`) overrides the planner's keyword classification. Unknown fields are rejected. Production currently accepts `language: "en"` only; `hi`, `kn` and the bonus languages → 422 `language_unavailable` (translation and multilingual voice arrive in Task 6). Development mock mode additionally accepts `hi`/`kn` with clearly labelled English text. Errors: see §11.
Response `202`:
```json
{"job_id": "j_7f3a9c", "lesson_id": "3f9a1c2b7d10", "variant": "hi-female-1", "cached": false, "mock": false}
```
`cached: true` → the variant is complete (preview files verified and `lesson.mp4` present) and the job is already `done`. If the same lesson and variant is already queued or running, that job's ids are returned (`cached: false`). `mock: true` only in development mock mode.

## 4. `GET /api/jobs/{job_id}` — progress (poll every 500 ms)
```json
{
  "job_id": "j_7f3a9c",
  "kind": "create",
  "status": "running",
  "queue_position": 0,
  "lesson_id": "3f9a1c2b7d10",
  "variant": "hi-female-1",
  "playable": false,
  "preview_ready": false,
  "export_status": "pending",
  "mock": false,
  "fallback": false,
  "fallback_reason": null,
  "progress": 0.0,
  "stages": [
    {"name": "plan",      "status": "done",    "ms": 9120, "rss_mb": 1810, "note": "qwen3:8b, 812 tokens"},
    {"name": "validate",  "status": "done",    "ms": 14,   "rss_mb": 1810, "note": "2 auto-fixes"},
    {"name": "translate", "status": "running", "ms": null, "rss_mb": null, "note": ""},
    {"name": "voice",     "status": "pending", "ms": null, "rss_mb": null, "note": ""},
    {"name": "timeline",  "status": "pending", "ms": null, "rss_mb": null, "note": ""},
    {"name": "export",    "status": "pending", "ms": null, "rss_mb": null, "note": ""}
  ],
  "warnings": [],
  "error": null,
  "error_detail": null,
  "total_ms": 9134,
  "device_profile": "gpu"
}
```
- `kind`: `create` | `revoice` | `edit`.
- `status`: `queued` | `running` | `done` | `error`.
- Stage `status`: `pending` | `running` | `done` | `cached` | `skipped` | `error`. (`translate` is `skipped` for English.)
- `playable` turns true when the preview is ready (see below); the UI opens the player then.
- **`preview_ready`** (Task 5A): true only after the preview files were verified on disk (`lesson.json`, `timeline.json`, `props.json`, `lesson.srt`, plus `narration.m4a`/`narration.wav` when `timeline.audio` is not null) and they agree with each other. It is not derived from the stage. It becomes true during or at the end of the `timeline` stage, before export starts, and stays true if export later fails.
- **`export_status`** (Task 5A): `pending` → `running` → `completed` | `failed`. `skipped` appears only in mock mode (no MP4 is rendered). Export failure sets `status: "error"` and `export_status: "failed"` but leaves `preview_ready` and `playable` true.
- **`mock`** (Task 5A): true for every development mock-mode job.
- **`error_detail`** (Task 5A): `{"stage": "plan", "code": "validation_failed", "message": "…"}` when a stage failed; `code` is the stage's own error code (planner codes, unchanged: `validation_failed`, `timeout`, `unavailable`, `ollama_rejected`, `ollama_error`, `unsupported_options`, `planner_error`; plus `plan_invalid`, `tts_failed`, `timeline_failed`, `preview_incomplete`, `preview_invalid`, `export_failed`). `error` repeats the message.
- `progress`: export progress 0–1 while `export` runs.
- `fallback: true` → `fallback_reason` holds one line for the banner, e.g. `"Planner returned invalid JSON twice"`. **Task 5A jobs never set it:** a failed stage ends the job as `status: "error"` with `error_detail`; no substitute lesson is served (planner-task4.md).
- Later stages of a failed job stay `pending`.
Unknown job → 404 `job_not_found`.

## 5. `GET /api/lessons/{lesson_id}?variant=hi-female-1`
```json
{
  "lesson_id": "3f9a1c2b7d10",
  "variant": "hi-female-1",
  "preview_ready": true,
  "export_status": "running",
  "mock": false,
  "lesson": {"…": "localized lesson, lesson-schema.md §1"},
  "timeline": {"…": "lesson-schema.md §6"},
  "media": {
    "audio_web": "/media/3f9a1c2b7d10/hi-female-1/narration.m4a",
    "audio_wav": "/media/3f9a1c2b7d10/hi-female-1/narration.wav",
    "mp4": "/media/3f9a1c2b7d10/hi-female-1/lesson.mp4",
    "srt": "/media/3f9a1c2b7d10/hi-female-1/lesson.srt"
  },
  "meta": {"source": "llm", "model": "qwen3:8b", "warnings": [], "stage_ms": {"plan": 9120, "validate": 14}, "variants": ["en-female-1", "hi-female-1"], "job_id": "j_7f3a9c"}
}
```
**Available as soon as the preview is ready, before the MP4 exists** (Task 5A): the response is built from the files on disk and is returned only when they verify, so `preview_ready` is always true here. `media.mp4` is `null` until `lesson.mp4` exists; any media URL whose file is missing is `null` (`audio_*` are `null` when `timeline.audio` is `null`). `export_status` is `completed` when the MP4 exists, otherwise the latest job's value (`pending` if none). `meta.stage_ms` covers the stages finished when the preview became ready. Without `variant`, return the most recent preview-ready variant. Unknown lesson/variant → 404 `lesson_not_found`; a lesson folder with no verified preview yet → 404 `preview_not_ready` (with `job_id` when known).

## 6. `POST /api/lessons/{lesson_id}/voice` — revoice (bonus)
```json
{"language": "kn", "voice": "female", "speed": 1.0}
```
→ `202` with the §3 response shape. The job has `kind: "revoice"`; `plan` and `validate` show `cached`.

## 7. `PATCH /api/lessons/{lesson_id}/scenes/{scene_id}` — edit one scene (bonus)
English fields only; send just what changed:
```json
{"variant": "hi-female-1", "scene": {"heading": "Step 1: Read the code", "narration": "…", "steps": [{"text": "…", "narration": "…"}]}}
```
→ `202 {"job_id": "…", "lesson_id": "3f9a1c2b7d10-v2", "variant": "hi-female-1", "cached": false}`. The edited plan is re-validated; validation errors → 422 with the error list (nothing is made).

## 8. `GET /api/lessons` — library (bonus)
```json
{"lessons": [{"lesson_id": "3f9a1c2b7d10", "title": "How does a Python for loop work?", "topic": "How does a Python loop work?", "level": "beginner", "target_seconds": 60, "source": "llm", "created_at": "2026-10-28T10:12:00+05:30", "variants": [{"variant": "hi-female-1", "has_mp4": true, "duration_s": 64.2}]}]}
```

## 9. Media
`GET /media/{lesson_id}/{variant}/{file}`, static from `cache/lessons/`. Files: `narration.m4a`, `narration.wav`, `lesson.mp4`, `lesson.srt`.
`?download=1` adds `Content-Disposition: attachment; filename="<topic-slug>_<lang>.mp4"` (or `.srt`).

## 10. Debug (dev only, off in the demo build unless needed)
- `GET /api/lessons/{lesson_id}/plan` → the English plan + validation report (fixes, errors, lint). Shown in the UI's "Plan JSON" panel.
- `POST /api/lessons` with `"debug_fail": "plan"` → forces the planner to fail, to show the fallback on purpose in the demo.

## 11. Errors (Task 5A)
All errors: `{"error": {"code": "…", "message": "…", …}}`.

| Status | `code` | When |
|---|---|---|
| 422 | `validation_error` | Bad body; `error.fields` is `[{"field": "topic", "message": "…"}]` |
| 422 | `language_unavailable` | Any language other than `en` in production |
| 422 | `mock_topic_unavailable` | Mock mode only: no fixture for the topic |
| 429 | `busy` | The worker and its waiting queue (`MAX_QUEUED_JOBS`, default 2) are full; `Retry-After` header (seconds) and `error.retry_after` |
| 503 | `runner_unavailable` | The worker is not accepting jobs (shutting down) |
| 404 | `job_not_found`, `lesson_not_found`, `preview_not_ready` | See §4, §5 |

CORS: the API allows the origins `http://localhost:5173`, `http://127.0.0.1:5173` and `http://localhost:3000` (methods `GET`, `POST`, `PATCH`; header `Content-Type`). The built app is same-origin and needs none.

New file in each variant folder (Task 5A): `meta.json` (`job_id`, `mock`, `source`, `model`, `warnings`, `stage_ms`), written when the preview is verified. The preview set is `lesson.json`, `timeline.json`, `props.json` (browser-player render props), `lesson.srt` and, when the timeline has audio, `narration.m4a` and `narration.wav`.
