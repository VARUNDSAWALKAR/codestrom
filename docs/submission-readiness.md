# Blu VisualTeacher - submission readiness, 28 October 2026

**PARTIALLY READY for the complete hackathon requirements. English/Hindi demo
flows are ready; Kannada remains unapproved and disabled.** Automatic semantic
visual planning is experimental and disabled. Do not pitch arbitrary-topic
visual mechanisms as verified. No new visual engine feature was added here.

## Actual application acceptance

- [x] Real FastAPI production startup, CPU profile, MOCK_PIPELINE=0.
- [x] Actual Vite UI connected to backend through /api and /media proxies.
- [x] /api/config available languages are en/hi; kn and bonus languages disabled.
- [x] One new topic submitted using actual form controls: Stack push and pop in
  Python, beginner, English, 60-second target, female, speed 1, Programming.
- [x] Fresh Ollama qwen3:4b-instruct-2507-q4_K_M plan: one attempt, 41.8 s.
- [x] Real Kokoro: 11 uncached beats / 32.566 s speech; measured timeline 1118
  frames; real Remotion/FFmpeg MP4. English final duration 37.269 s satisfies 30-90 s.
- [x] Job j_9cf6bbe8fac1 completed with preview_ready=true, export_status=completed.
- [x] UI play/pause, next scene, replay, audio playback, MP4/SRT downloads passed.
  Native browser MP4 playback also advanced; both full MP4s decode successfully.
- [x] Hindi Water Cycle c1f63f0ed69b/hi-female-1 served through the actual UI,
  cached=true; job j_1cfebfb56e42. All stages cached, no new translation/TTS/LLM.
  Duration 73.109 s; Devanagari captions inspected; protected English terms remain.
- [x] Both UI downloads match backend MP4 and SRT bytes. Both are 1280x720
  H.264/AAC with real narration. No mocked successful API responses were used.
- [x] Ordinary lessons have no authored visual sidecar and use legacy title,
  code-walkthrough and diagram scenes without silently substituting an array.
- [x] The original 24.58 s authored VQ3 array demo remains unchanged/playable.
  It is a controlled demo, not automatic visual generation or a 30-90 s acceptance.
- [x] Fixed the app player's omission of existing optional visualSpec props.
  Ordinary playback and a separately labeled controlled sample were verified
  through the actual LessonPlayer after the one-line forwarding fix.
- [x] No .env, language approval, model, planner prompt or original cache edits.

## Verified checkout and videos

Run the integrated checkout on branch `sync/varun-approved-20261028`:
`C:\Users\ROG\AppData\Local\Temp\blu-approved-merge-20261028`.

The original `C:\Users\ROG\VisualTeacher-varun` checkout remains at b5e0b07
with the owner's original uncommitted work preserved. Integration source was
reviewed/committed at d782473 (parents 97e1116 and 95c2408). A final stabilization
commit adds this checklist and the player prop-forwarding fix. Nothing was pushed.
Secrets, .env, caches, models, scratch media, node_modules, dist and build were excluded.

Acceptance root in the original checkout:
`scratch/final-mvp/96754482-8ea4-4790-a73b-7be73b917ed6/`.

| Video | Location | Result |
| --- | --- | --- |
| Fresh English stack lesson | download-en.mp4 | 37.269 s, H.264/AAC 720p, UI-generated/downloaded |
| Cached approved Hindi Water Cycle | download-hi.mp4 | 73.109 s, H.264/AAC 720p, UI-played/downloaded |
| Controlled authored array | ../../vq3-narrated/ff927c5c-fce6-4e95-b0e9-6418ba6183cf/lesson.mp4 relative to acceptance root | 24.58 s, separate authored demonstration |

Evidence: ui-acceptance.json, media-verification.json, audio-verification.json,
postfix-ui.json, representative en/hi frames and UI screenshots. Browser requests
were local-only; no external application requests were observed. This was not a
physical network-adapter-disconnection test.

## Startup commands (PowerShell, two terminals)

Services are currently running at http://127.0.0.1:8000 and http://127.0.0.1:5173.
These commands are for restarting after stopping only the demo's own processes.
Keep the acceptance CACHE_DIR to reuse the verified videos and avoid inference.

Backend terminal:

```powershell
Set-Location 'C:\Users\ROG\AppData\Local\Temp\blu-approved-merge-20261028'
$env:DEVICE = 'cpu'
$env:PYTHONUTF8 = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:MOCK_PIPELINE = '0'
$env:APPROVED_LANGUAGES = 'en,hi'
$env:CACHE_DIR = 'C:\Users\ROG\VisualTeacher-varun\scratch\final-mvp\96754482-8ea4-4790-a73b-7be73b917ed6\cache'
& 'C:\Users\ROG\Kavach\kavach-env\Scripts\python.exe' -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
Set-Location 'C:\Users\ROG\AppData\Local\Temp\blu-approved-merge-20261028\web'
npm.cmd run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. For English replay, choose the exact Stack topic and
Programming. For cached Hindi, choose Water Cycle / Hindi and set More options /
Subject = Science (do not leave the previous Programming selection remembered).
Both use beginner / 60-second target / female / speed 1. Play, pause, next scene,
replay, then download MP4 and SRT. The target is approximate; actual audio sets duration.

Preparation, if builds need recreating, from the web directory: `npm.cmd run build`
then `npm.cmd run bundle`. These passed using already-installed packages. Do not
install/update/download dependencies during the demonstration. Ollama must be
running locally on port 11434; use `ollama serve` only if it is not already running.

## Offline prerequisites and test totals

- Existing Kavach Python environment and installed backend dependencies.
- Local Ollama CPU tag qwen3:4b-instruct-2507-q4_K_M.
- Local Kokoro ONNX and voices under C:/Users/ROG/Kavach/models/kokoro.
- Local IndicTrans2 and installed IndicTransToolkit for fresh Hindi translation;
  fresh translation inference was not rerun in this final acceptance.
- Installed Node/Remotion packages at matching 4.0.539, local Chrome, FFmpeg/ffprobe,
  local Noto fonts. Vite dist and Remotion build are prepared and remain uncommitted.
- Full integrated backend regression: **396 passed, 1 skipped, 42 subtests passed**
  in 46.78 s. Existing skip: renderer-presence test at test_task3.py:118.
  The uncommitted failed VQ1.2 pilot/tests remain protected in the original
  checkout and are not part of this verified integration's test count.
- Frontend **67 passed**; TypeScript and Vite build passed after stabilization.
  Existing module-directive/large-chunk warnings are non-blocking. Remotion bundle passed.
- Cold translator health remains ready=false because cached Hindi did not load
  it. Aggregate health.ok therefore remains false; planner/Kokoro and renderer
  readiness are true. This is not a fabricated all-model-ready report.

## Limits and remaining submission gates

- [ ] Native Kannada review/explicit owner approval is still pending. Existing
  technical Task 7 artifacts do not constitute human approval. Do not enable kn
  automatically. The official three-language requirement is not yet accepted.
- [ ] Automatic semantic visual planning remains disabled after failed VQ1/1.1/1.2
  quality gates. Only the authored English array slice is specialized/verified.
- [ ] Generated educational content still needs review. In this fresh Stack
  lesson, the displayed code has a second final pop line not covered by narration
  highlights; the narrated four-step example is internally consistent through
  its first pop. No output was edited or regenerated to hide this limitation.
- [ ] Legacy generic diagrams, inherited repeated scenes and protected English
  technical labels remain; no optics/physics/chemistry solver is claimed.
- [ ] New Hindi generation, native pronunciation review, phone performance and
  arbitrary-topic semantic correctness were not newly accepted by this run.

Fallback means absent/invalid/unsupported specialized visuals retain the trusted
legacy scene. Production generation failures report structured errors; this
implementation does not silently substitute an unrelated successful lesson.
English/Hindi technical demonstration is ready. Full requirements remain partially
ready until the Kannada approval gate and final content/presentation review.
