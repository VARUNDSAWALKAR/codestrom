# Frontend integration — lesson API (Tasks 5A–6)

For Varun. Contract of record: [api-contracts.md](api-contracts.md) §3–5 and §11. This page is the practical walkthrough.

> **Status (Task 6).** Production approval defaults to English. Hindi localization,
> Kokoro narration and preview are technically connected, but Hindi stays disabled
> until human review and explicit `APPROVED_LANGUAGES=en,hi`. The owner has now
> approved Hindi and this deployment has that setting. Task 7 adds Kannada voice,
> which remains separately unapproved and disabled pending native review.
> Real English MP4 export was verified in 5C; Task 6 verifies Hindi preview only,
> without MP4 rendering. Development mock mode remains separate and labelled.

## Running the backend
- **Ollama must already be running** with the planner model pulled (`qwen3:4b-instruct-2507-q4_K_M` on CPU). The backend does not start or pull it.
- Choose the CPU profile explicitly: `$env:DEVICE="cpu"` (or `DEVICE=cpu` in `.env`). With `DEVICE=auto` a machine with CUDA picks the GPU model `qwen3:8b`.
- Start (one process, no `--reload`, no extra workers: job state is in memory), PowerShell from the repo root:
  ```powershell
  $env:DEVICE = "cpu"; $env:MOCK_PIPELINE = "0"; $env:PYTHONUTF8 = "1"; Remove-Item Env:LOW_RAM -ErrorAction SilentlyContinue
  & "C:\Users\ROG\Kavach\kavach-env\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
  ```
  `PYTHONUTF8=1` is required on Windows: lessons contain Unicode (`CO₂`, arrows, code) and the default cp1252 console/log encoding fails on it.
- **Kokoro loads on the first voice request** (not at startup) and is reused afterwards, so the first lesson after a restart is slower. `tts_kokoro.ready` in `/api/health` turns true only after that load succeeds.
- **Real MP4 export needs uvicorn listening on `127.0.0.1:<port>`** (default 8000): the renderer downloads the narration WAV from `http://127.0.0.1:8000/media/...`, and the exporter checks that URL first. It also needs the built Remotion bundle (`cd web && npx remotion bundle`, output `web/build`). Verified in Task 5C.
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
`GET /api/config` lists all seven. Production availability and POST prechecks
share one policy: configured `APPROVED_LANGUAGES` (default en) intersected with
implemented voice languages en/hi/kn (kn requires ENABLE_PARLER=1). Code defaults
to en; this deployment already has owner-approved en,hi. Only after separate review
may the owner explicitly set en,hi,kn and restart. Bonus voices stay unavailable.
Build the picker from `available`, never `tier` or model health.
Mock mode still offers labelled English fixtures for en/hi/kn. Reload config after
a restart. Translation never replans: all variants share a canonical English ID.

## Health gating
`GET /api/health` has `ok = planner && translator && tts_kokoro`. Lazy model loads
and LOW_RAM release can leave `ok=false` while generation is available. Do not
gate the UI on `ok`. Gate on:
- `models.planner.ready`: true only while Ollama answers and lists the planner model (checked at most every 5 s). Disable "Create" when false.
- `models.tts_kokoro.ready`: false until the first voice request has loaded Kokoro, then true. It is **not** a reason to block "Create" (it is false on a fresh start); show it as informational ("voice warms up on first use").
- `models.translator.ready` becomes true only after local initialization and false
  after synchronized release; cache hits may need no load. Show it as informational.
- `models.tts_parler.enabled` reflects CPU/CUDA Kannada capability; `ready` is true
  only after successful local initialization and false after release. A fresh false
  value is not a failed model or a language-approval decision.
`mock_pipeline: true` means fixtures are active; show the MOCK banner. Language
availability comes from config and explicit approval, independently of health.

## CORS
Allowed origins: `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000` (Remotion Studio). Methods `GET`, `POST`, `PATCH`; header `Content-Type`. The built app is same-origin and needs none of this. Nothing else is allowed (AGENTS.md rule 1).

## Development mock mode (optional, never the default)
Lets you build the UI without Ollama or TTS. It accepts labelled hi/kn English
fixtures independently of production approval. It replays `data/samples/*.props.json`
without calling Ollama, TTS or the renderer.

- **Enable:** set `MOCK_PIPELINE=1` in `.env` (or `$env:MOCK_PIPELINE="1"` in the shell before `uvicorn …`). Restart the backend. The log shows a `MOCK_PIPELINE is enabled` warning and `GET /api/health` returns `"mock_pipeline": true`.
- **Disable:** remove the line (or set `MOCK_PIPELINE=0`) and restart. It is off by default and must be off for acceptance runs.
- **Topics:** only `Water Cycle`, `Python loop` (or `Python for loop`) and `Newton's second law`. Any other topic gets `422 mock_topic_unavailable`; it is never answered with an unrelated sample.
- **Markers:** `mock: true` on the submit response, the job and the lesson response; `lesson.source` is `"sample"`, `lesson.model` is `"mock-pipeline"`, and `meta.warnings` start with `MOCK:`. Show a visible "MOCK DATA" banner whenever `mock` is true.
- **Behaviour:** text is always English (language `hi`/`kn` only changes the label, with a `MOCK:` warning), there is no audio (`audio_* = null`, silent playback), and no MP4 (`export_status: "skipped"`, `media.mp4 = null`).
- Mock lessons get their own lesson ids and can never be served as real cached lessons.

## Verified in Task 5C (real uvicorn, Ollama, Kokoro, Remotion, FFmpeg; CPU profile)
Two real production jobs were run over HTTP against `127.0.0.1:8000` and produced playable, ffprobe-valid MP4s. Nothing below involved mock mode or `TestClient`.

| | Water Cycle (`science`) | Binary Search (`programming`) |
|---|---|---|
| Lesson id / variant | `c1f63f0ed69b` / `en-female-1` | `d09d4030959b` / `en-female-1` |
| plan | cached (planner cache hit, ~2 ms) | cached (~3 ms) |
| voice (Kokoro, first job also loads it) | 10.9 s | 13.2 s |
| timeline | 1.4 s | 1.6 s |
| export (Remotion + FFmpeg) | 114.5 s | 132.7 s |
| wall clock, POST to `done` | 127.2 s | 147.9 s |
| first `preview_ready: true` | 12.7 s (MP4 appeared ~114 s later) | 15.2 s (MP4 ~133 s later) |
| MP4 | 1,398,933 B, 50.2 s | 1,673,394 B, 58.5 s |

A fresh planner generation takes about 30 s on top of this (Task 5B smoke: plan 31 s). Budget **~3 minutes per new 60 s lesson** on this CPU machine. Backend RSS ~620-680 MB once Kokoro is loaded; the renderer (node + Chromium) adds ~800 MB while exporting.

- **Preview before MP4 (verified live).** While `export_status` was `running`, `GET /api/lessons/{id}` returned 200 with `preview_ready: true`, `media.audio_web`, `media.audio_wav`, `media.srt` set, `media.mp4: null`; the audio, SRT, `timeline.json` and `props.json` URLs all returned 200 with bodies. Start playing as soon as `preview_ready` is true.
- **MP4 URL:** `/media/{lesson_id}/{variant}/lesson.mp4` (`video/mp4`; **HTTP Range requests work (206)**, so a `<video>` element can seek). It appears in `media.mp4` only when the file passes the exporter's verification (see below). Format: H.264 High, 1280x720, yuv420p, 30 fps, AAC 48 kHz stereo, faststart, duration within 0.02 s of the timeline.
- **Repeat request:** the identical request returned `202` with `cached: true` in ~50 ms, a `done` job with every stage `cached` and no renderer or model activity.
- **What counts as a finished MP4:** `props.sha1` matches the current render props **and** the MP4's top-level boxes are complete (`moov` + `mdat` tile the file) **and** ffprobe validation passes. A truncated or stale file is not served as `media.mp4` and the next request re-renders it (a job warning says so). Found in 5C: ffprobe alone accepts a truncated faststart MP4, hence the extra structure check.
- **Health:** `tts_kokoro.ready` stayed `false` until the first lesson had loaded Kokoro, then `true`; `planner.ready` is live from Ollama; `translator.ready` is `false`, so `ok` is `false` (do not gate on it); `renderer.bundle_ready` is `true` when `web/build/index.html` exists.
- **API contract spot checks (live):** `hi`/`kn` -> 422 `language_unavailable` (Hindi/Kannada message); `ta` -> 422 `language_unavailable` (bonus-language message); bad fields -> 422 `validation_error` with `fields`; unknown job -> 404 `job_not_found`; unknown or malformed lesson id -> 404 `lesson_not_found`; CORS preflight allows exactly `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000` and rejects other origins (no `Access-Control-Allow-Origin`).

### Not available yet / known limitations
- **`?download=1` is not implemented.** `GET /media/.../lesson.mp4?download=1` returns the file without `Content-Disposition`. api-contracts.md section 9 describes it, but it is **pending**; use an `<a download="...">` attribute on the client for now.
- **Approval and voice limits.** English is approved by default; Hindi needs
  explicit post-review approval (already recorded here). Kannada voice is integrated
  in Task 7 but still requires separate approval. Mock hi/kn remains
  clearly labelled English fixture content.
- **Lesson content quality is the 4B model's.** Seen in the acceptance runs: a diagram scene headed "Title Card" and two scenes with identical steps (Water Cycle), and code step highlights that are one line too early (Binary Search: each step's `lines` points at the line above the one named in the step text). The renderer draws exactly what the lesson says; fixing this is a planner task (prompt or an extra validator), not a frontend one.
- Code scenes render the code with line numbers, a highlight bar and a State panel; the Output panel is empty unless a step supplies `output`.
- `POST .../voice`, `PATCH .../scenes` and `GET /api/lessons` (library) are not implemented.

## Verified in Task 6 (Hindi preview, no MP4)

Real TestClient acceptance used Water Cycle `c1f63f0ed69b/hi-female-1`, with Hindi
approval confined to its Settings. Cached canonical plan reused with zero Ollama
calls; real local IndicTrans2 initialized and its M2 translation cache reused;
real Kokoro plus timeline produced a non-silent 73.1 s Hindi WAV, 14 captions,
matching SRT and validated render props. Preview was ready before deliberate
export skip; all audio/SRT/timeline/props HTTP URLs were 200/nonempty. MP4 remained
null and no real render occurred.

Plan 4 ms, validation 1 ms, translation cache 596 ms, voice 14.357 s, timeline
1.591 s. Complete localization, 0/11 eligible English fallback beats; five note
length warnings, no over-90-second warning. Warnings should be shown; labels are
not truncated by the backend. Code/expressions/technical terms stay exact.

Translation exceptions use stage `translate`, code `translate_failed`. Excessive
retained English uses `translate_incomplete` (`LOCALIZE_MAX_ENGLISH_FRACTION=0.2`,
eligible narration beats only); voice/timeline/export remain pending. Within-limit
partial localization can proceed with warnings. Diagnostics are in localization.json.

Review pack: `scratch/review/hi/` (20 pairs, technical examples, real WAV/SRT,
checklist). Human review is pending; technical readiness never enables Hindi.
No frontend edits or browser layout/listening approval were performed in Task 6.

## Task 7 Kannada acceptance

One real CPU preview from cached Water Cycle plan/translation succeeded:
`c1f63f0ed69b/kn-female-1`, Parler Anu, no fresh Ollama/translation calls. Voice
stage 268.159 s (cold load 7.150 s included), timeline 1.393 s; preview wall
271.060 s. Audio/timeline 72.7 s, 17 Kannada captions, tempo 1.0. All media URLs
were 200/nonempty before MP4 existed. Seven note-length warnings are preserved.

One real existing-renderer export then passed: 1,942,066 bytes, H.264 High/AAC LC,
1280x720, yuv420p, 30 fps; video 72.700 s, audio/container 72.704 s, full decode
and Range 206 passed. Five frames under `scratch/accept/kannada/` show Kannada
glyphs, fitting headings/captions, expected step highlights; no missing-glyph boxes
or obvious clipping observed. No web modification was needed. This is sampled
visual/timing verification, not native pronunciation or phone playback approval.

Review pack `scratch/review/kn/` includes actual MP4/WAV/SRT, 20 pairs, technical
examples and known Task 6 fallbacks (Binary Search two labels, Python loop one
narration beat), screenshots/statistics/checklist. Kannada remains unapproved;
production config continues to expose en/hi only. Native reviewer approval is the
next step. Existing generic diagrams and “Title Card” heading are source-content
issues from the English planner, preserved for later content/VQ work.
