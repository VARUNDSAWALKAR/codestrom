# API contracts — Blu VisualTeacher

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
  "queue_length": 0
}
```
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
Rules: `topic` 3–120 chars after trimming; enums as in §2; `target_seconds` 30–90; `speed` 0.8–1.2. Bad input → 422 with field errors.
Response `202`:
```json
{"job_id": "j_7f3a9c", "lesson_id": "3f9a1c2b7d10", "variant": "hi-female-1", "cached": false}
```
`cached: true` → the variant already exists and the job finishes immediately as `done`.

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
  "total_ms": 9134,
  "device_profile": "gpu"
}
```
- `kind`: `create` | `revoice` | `edit`.
- `status`: `queued` | `running` | `done` | `error`.
- Stage `status`: `pending` | `running` | `done` | `cached` | `skipped` | `error`. (`translate` is `skipped` for English.)
- `playable` turns true after `timeline`; the UI opens the player then.
- `progress`: export progress 0–1 while `export` runs.
- `fallback: true` → `fallback_reason` holds one line for the banner, e.g. `"Planner returned invalid JSON twice"`.
- `status: "error"` happens only if even the fallback fails; `error` has the message.
Unknown job → 404.

## 5. `GET /api/lessons/{lesson_id}?variant=hi-female-1`
```json
{
  "lesson_id": "3f9a1c2b7d10",
  "variant": "hi-female-1",
  "lesson": {"…": "localized lesson, lesson-schema.md §1"},
  "timeline": {"…": "lesson-schema.md §6"},
  "media": {
    "audio_web": "/media/3f9a1c2b7d10/hi-female-1/narration.m4a",
    "audio_wav": "/media/3f9a1c2b7d10/hi-female-1/narration.wav",
    "mp4": "/media/3f9a1c2b7d10/hi-female-1/lesson.mp4",
    "srt": "/media/3f9a1c2b7d10/hi-female-1/lesson.srt"
  },
  "meta": {"source": "llm", "model": "qwen3:8b", "warnings": [], "stage_ms": {"plan": 9120, "validate": 14}, "variants": ["en-female-1", "hi-female-1"]}
}
```
`media.mp4` is `null` until export finishes. Without `variant`, return the most recent variant. Unknown → 404.

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
