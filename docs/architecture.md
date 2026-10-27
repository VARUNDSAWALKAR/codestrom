# Architecture — Blu VisualTeacher

> Task 4 override: see [offline planner contract](planner-task4.md). Planner calls use 180 s, keep_alive 10m, one repair, failure-only raw logs, and English content with requested-language metadata. Failed requests return structured errors; no unrelated fallback. Task 5 orchestration is not implemented.

Build file · How the parts fit, where files live, and how it runs offline on GPU or CPU.
Related: `pipeline.md` (each stage), `lesson-schema.md` (JSON contracts), `../AGENTS.md` (coding rules).

---

## 1. The big picture
```
 Browser: React app + Remotion Player
   │  POST /api/lessons {topic, level, language, target_seconds, voice, speed}
   │  GET  /api/jobs/{id}  (poll every 500 ms: stage, timings, playable, fallback)
   ▼
 FastAPI  backend/app/main.py ── job queue ── 1 worker thread (one job at a time)
   │
   ├─ plan       planner/   → Ollama 127.0.0.1:11434 (qwen3:8b on GPU / qwen3:4b on CPU, JSON schema format)
   ├─ validate   planner/   → Pydantic + auto-fix + 1 repair call ──fail──► fallback lesson
   ├─ translate  localize/  → IndicTrans2 dist-200M (terms + code masked)
   ├─ voice      speech/    → Kokoro (CPU) / Indic Parler-TTS (GPU), one clip per beat
   ├─ timeline   timeline/  → beat times, captions, narration.wav/.m4a, .srt   ═► playable
   └─ export     export/    → node web/render/render.mjs (Remotion, headless Chrome)
                              → faststart + ffprobe check                     ═► done
   │
   ▼
 cache/lessons/<id>/<variant>/…   served at /media/<id>/<variant>/…
```

## 2. Four parts, kept separate
The rubric checks for "clean separation of planner, renderer and exporter".
| Part | Code | In → out | Knows nothing about |
|---|---|---|---|
| **Planner** | `backend/app/planner/` | topic, level, length → validated English `Lesson` | audio, video, languages |
| **Localizer + voice + timeline** | `backend/app/localize/`, `speech/`, `timeline/` | `Lesson` + language + voice → localized lesson, clips, `timeline.json`, `.srt` | the LLM, React |
| **Renderer** | `web/src/lesson/` | (localized lesson, timeline, frame) → pixels | Python, models |
| **Exporter** | `web/render/render.mjs` + `backend/app/export/` | render props → checked `lesson.mp4` | planning, translation |

The browser player and the MP4 use the same renderer components, so the preview and the export can't drift apart.

## 3. Folder layout
```
VisualTeacher/
├── AGENTS.md, CLAUDE.md          rules for coding agents
├── README.md                      submission README (written at the event: setup, models + licences, laptop specs)
├── .env                           paths + settings (never commit)
├── .gitignore                     .env, cache/, models/, node_modules/, web/dist/, web/build/, __pycache__/
├── docs/                          these plan files
├── data/
│   ├── fallback/python_loop.en.json
│   └── samples/                   2 more lessons, mock timelines, render props
├── backend/
│   ├── requirements.txt           pip freeze of the packages we added
│   └── app/
│       ├── main.py                routes, /media static, serves web/dist at /
│       ├── config.py              .env → settings; device profile
│       ├── jobs.py                queue, worker, stage timings, peak RSS, runs.jsonl
│       ├── cache.py               keys, folders, index.json
│       ├── planner/               ollama_client.py · prompt.py · lesson.schema.json · schema.py · validate.py · fallback.py
│       ├── localize/              translate.py · terms.py
│       ├── speech/                engines.py · kokoro_engine.py · parler_engine.py · textnorm.py · audio.py
│       ├── timeline/              build.py · captions.py · srt.py
│       └── export/                render.py · ffmpeg.py
├── web/
│   ├── package.json, vite.config.ts, remotion.config.ts (entry point src/remotion/index.ts)
│   ├── public/fonts/              Noto Sans (+ Devanagari, Kannada, Tamil, Telugu, Bengali, Mono)
│   ├── src/app/                   App.tsx · pages/InputPage.tsx · pages/LessonPage.tsx · api.ts
│   ├── src/lesson/                Lesson.tsx · types.ts · theme.ts · fonts.ts · timing.ts
│   │   ├── scenes/                TitleCard · CodeWalkthrough · Diagram · Formula · Recap (· Quiz)
│   │   └── chrome/                StepHeading · CaptionBar · ProgressBar
│   ├── src/remotion/              index.ts · Root.tsx (composition "Lesson", calculateMetadata)
│   └── render/render.mjs          Node renderer CLI (AGENTS.md → Contracts)
└── cache/                         generated (never commit)
```
`backend/` and `web/` are created at the event: all code is written during the 24 hours.

## 4. Processes
| Process | Started by | Notes |
|---|---|---|
| Ollama | Windows service (or `ollama serve`) | `127.0.0.1:11434` |
| Backend | `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000` | FastAPI + 1 worker thread; warms models at startup |
| Renderer | backend runs `node web/render/render.mjs` per export | uses the prebuilt bundle `web/build`; exits when done |
| Browser | the learner | demo: `http://127.0.0.1:8000/` (built app); dev: Vite on `:5173` |

**Warm-up at startup** (shown as health badges in the UI): ping Ollama and run a 1-token generate with `keep_alive: "30m"`, load Kokoro, load IndicTrans2, load Parler only on the `gpu` profile with `ENABLE_PARLER=1`. Without warm-up, the first lesson pays 10–30 s of model loading.

## 5. Device profiles and memory
`DEVICE=auto` → `gpu` if `torch.cuda.is_available()`, else `cpu`. Force with `DEVICE=cpu` (for the CPU-only proof, also hide the GPU: `set CUDA_VISIBLE_DEVICES=-1` before starting Ollama and the backend).

| | `gpu` (Satwik's laptop, demo) | `cpu` (the "works without GPU" rule) |
|---|---|---|
| Planner (Ollama) | `qwen3:8b`, `think: false` | `qwen3:4b-instruct-2507-q4_K_M`, `options.num_gpu = 0` |
| IndicTrans2 dist-200M | CUDA, fp16 | CPU, fp32 |
| Kokoro | CPU (onnxruntime) — fast on any laptop | CPU |
| Parler | CUDA (kn + bonus languages) | **not loaded** (~7× slower than real time on CPU) |
| Remotion export | concurrency = cores ÷ 2 | 2 if RAM ≤ 8 GB |
| `LOW_RAM` | 0 | 1 on 8 GB machines |

`LOW_RAM=1`: unload the LLM after `validate` (`keep_alive: 0`), unload the translator after `translate`.

**VRAM (8 GB):** `qwen3:8b` at 4k context ≈ 6 GB + IndicTrans2 fp16 ≈ 0.5 GB already fills most of it; Parler (bf16 ≈ 2 GB, fp32 ≈ 3.7 GB) doesn't fit on top. **Rule:** on the `gpu` profile, unload the LLM (`keep_alive: 0`) after `validate` whenever the voice stage will use Parler. Reloading it for the next plan costs ~5–10 s. If VRAM is still short, use `qwen3:4b` on the GPU too.
**RAM, CPU profile (estimate, measure tonight):** Ollama ≈ 3 GB + translator ≈ 1 GB + Kokoro ≈ 0.4 GB + backend ≈ 0.3 GB + render ≈ 1 GB. With `LOW_RAM=1` the peak stays near 4–5 GB.

## 6. Configuration (`.env`)
No API keys: nothing in this project calls an external service.
```
# Models
OLLAMA_URL=http://127.0.0.1:11434
PLANNER_MODEL_GPU=qwen3:8b
PLANNER_MODEL_CPU=qwen3:4b-instruct-2507-q4_K_M
PLANNER_BACKUP_MODEL=llama3.2:3b
MODELS_DIR=C:\Users\ROG\Kavach\models
KOKORO_MODEL=kokoro\kokoro-v1.0.onnx
KOKORO_VOICES=kokoro\voices-v1.0.bin
INDICTRANS_MODEL=indictrans2
PARLER_MODEL=indic-parler-tts
ENABLE_PARLER=1

# Runtime
DEVICE=auto
LOW_RAM=0
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
PORT=8000
CACHE_DIR=cache
WEB_DIST=web\dist
RENDER_BUNDLE=web\build
RENDER_SCRIPT=web\render\render.mjs
RENDER_CONCURRENCY=0
EXPORT_FPS=30

# Defaults
DEFAULT_LANGUAGE=en
DEFAULT_TARGET_SECONDS=60
```
`RENDER_CONCURRENCY=0` means automatic. Model paths are relative to `MODELS_DIR`. `config.py` must set `HF_HUB_OFFLINE` and `TRANSFORMERS_OFFLINE` in `os.environ` **before** anything imports transformers.

## 7. Ports and URLs
| Port | What |
|---|---|
| 11434 | Ollama |
| 8000 | backend: `/api/*`, `/media/*`, and the built app at `/` |
| 5173 | Vite dev server (proxies `/api` and `/media` to 8000) |
| 3000 | Remotion Studio (scene work) |

During the build, Varun's Vite can point its proxy at Satwik's laptop (`http://<satwik-ip>:8000`) over the same Wi-Fi. The demo runs everything on Satwik's laptop.

## 8. API at a glance
Full shapes in `api-contracts.md`.
```
GET   /api/health                              models ready, device profile, offline flags
GET   /api/config                              languages (core/bonus), voices, limits, defaults
POST  /api/lessons                             {topic, level, language, target_seconds, voice, speed} → {job_id, lesson_id}
GET   /api/jobs/{job_id}                       status, stages [{name, status, ms, rss_mb}], playable, fallback, reason, progress
GET   /api/lessons/{lesson_id}?variant=…       localized lesson + timeline + media URLs
POST  /api/lessons/{lesson_id}/voice           {language, voice, speed} → job (revoice, no re-planning)      bonus
PATCH /api/lessons/{lesson_id}/scenes/{id}     edited English fields → job for the new version               bonus
GET   /api/lessons                             cached lesson library                                          bonus
GET   /media/{lesson_id}/{variant}/{file}      narration.m4a/.wav, lesson.mp4, lesson.srt
```

## 9. Setup and offline prep
**Python** (reuse the Kavach venv: it already has torch, transformers 4.46.1, kokoro-onnx, parler_tts, IndicTransToolkit):
```
& C:\Users\ROG\Kavach\kavach-env\Scripts\Activate.ps1
pip install fastapi "uvicorn[standard]" httpx psutil
```
Plain `activate` silently does nothing in PowerShell; use `Activate.ps1` (or `& $py -m pip …`). Never `pip install -U transformers` (it breaks Parler).

**Ollama:**
```
ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama run qwen3:4b-instruct-2507-q4_K_M "Reply with OK"
ollama list
```
`ollama list` must show `qwen3:8b`, `qwen3:4b-instruct-2507-q4_K_M` and `llama3.2:3b`.

**npm prefetch (tonight, in a throwaway folder outside the repo):**
```
mkdir C:\Users\ROG\prefetch-web
cd C:\Users\ROG\prefetch-web
npm init -y
npm i react react-dom remotion@4 @remotion/cli@4 @remotion/player@4 @remotion/bundler@4 @remotion/renderer@4 @remotion/fonts@4 vite @vitejs/plugin-react typescript @types/react @types/react-dom tailwindcss @tailwindcss/vite prism-react-renderer playwright
npx remotion versions
npx remotion browser ensure
npx playwright install chromium
```
This fills the npm cache so the event install (`npm i --prefer-offline`) works on slow Wi-Fi. `npx remotion browser ensure` downloads Chrome Headless Shell: **note the folder it prints.** At the event, run it again inside `web/`; if it tries to download on bad Wi-Fi, copy that folder over instead. Playwright's Chromium is only for the Plan B exporter.

**Fonts:** download Noto Sans, Noto Sans Devanagari, Noto Sans Kannada, Noto Sans Tamil, Noto Sans Telugu, Noto Sans Bengali and Noto Sans Mono (all OFL) into `C:\Users\ROG\Kavach\fonts` (Latin, Devanagari and Kannada are already there). At the event, copy them to `web/public/fonts/`.

**Offline check (5 min, Wi-Fi off):** `ollama run` answers; Python loads Kokoro and IndicTrans2 with `HF_HUB_OFFLINE=1`; `npx remotion versions` runs inside `prefetch-web`.

## 10. Milestones
| When | Must work |
|---|---|
| **H+2** | `/api/health` answers · the `Lesson` composition plays `data/samples/python_loop.props.json` in Remotion Studio |
| **H+5 — PS gate 1** | Fallback lesson, English: real Kokoro audio → timeline → **MP4** (1280×720, H.264/AAC) |
| **H+8** | Typed topic → LLM → validated plan → English MP4, no manual steps; a broken plan plays the fallback |
| **H+12** | Same lesson in Hindi and Kannada: right script, captions and visuals in sync, MP4 for each |
| **H+16** | All core done; CPU-only run timed (`test-log.md`); bonus work may start |
| **H+20 — PS gate 2** | Feature freeze: only fixes after this |
| **H+22** | Both submission MP4s made (judges' topic + ours, each in English and one Indian language) |
