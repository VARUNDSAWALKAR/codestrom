# AGENTS.md — Blu VisualTeacher

> Task 4 override: see [offline planner contract](docs/planner-task4.md). Planner calls use 180 s, keep_alive 10m, one repair, failure-only raw logs, and English content with requested-language metadata. Failed requests return structured errors; no unrelated fallback. Task 5 orchestration is not implemented.

Read this before writing any code. The plan files in `docs/` are the source of truth. If code and docs disagree, stop and ask, or update the doc in the same commit.

## What we're building
An offline system that turns a typed concept into a 30–90 s narrated, animated lesson in English and Indian languages. It plays in the browser and exports as a 1280×720 MP4.
Pipeline: **plan** (local LLM → JSON) → **validate** → **translate** → **voice** → **timeline** → **export**. Details: `docs/pipeline.md`.

## Hard rules (breaking one disqualifies the team)
1. **No network calls except localhost.** No OpenAI, Gemini, Claude, ElevenLabs, Google Translate, Google/Microsoft voices, CDNs, Google Fonts or telemetry. Allowed: `127.0.0.1:11434` (Ollama), `127.0.0.1:8000` (our backend), `localhost:5173` (Vite dev), `localhost:3000` (Remotion Studio).
2. **Never execute model output.** No `eval`, `exec`, `compile`, `new Function`, `dangerouslySetInnerHTML`, dynamic `import()` or `subprocess` with model text. Model-written Python may be checked with `ast.parse` only (parsing, never running).
3. **LLM output is data.** Parse JSON → validate with the Pydantic models in `backend/app/planner/schema.py` → only validated objects go further. Visuals come only from our components: the model picks a scene type and fills its fields.
4. **Audio sets duration.** Never hard-code a scene or step duration. Every timing comes from `timeline.json` (`docs/lesson-schema.md` §6).
5. **CPU-only must work.** Every model loader takes its device from config (`DEVICE=auto|cuda|cpu`). Nothing may require CUDA.
6. **Offline.** `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. Load models only from local paths in `.env`. Fonts are local files in `web/public/fonts/`.
7. **Licences.** Any new model, voice, font or package → add it to `docs/licenses.md` in the same commit.

## Stack (don't add frameworks without asking)
- **Backend:** Python 3.11 (venv `C:\Users\ROG\Kavach\kavach-env`), FastAPI, Pydantic v2, httpx (Ollama client), kokoro-onnx, parler_tts, IndicTransToolkit, numpy, soundfile, psutil. FFmpeg/ffprobe via `subprocess`. **transformers is pinned at 4.46.1 by Parler-TTS: never upgrade it.**
- **Web:** Vite + React + TypeScript (strict). Remotion 4: `remotion`, `@remotion/player`, `@remotion/cli`, `@remotion/bundler`, `@remotion/renderer`, `@remotion/fonts`, **all at the exact same version** (`npx remotion versions` must show no mismatch). The app shell may use Tailwind. Scene components use inline styles from `web/src/lesson/theme.ts` only.
- **LLM:** Ollama. Model by device profile: `PLANNER_MODEL_GPU` (`qwen3:8b`, send `think: false`) or `PLANNER_MODEL_CPU` (`qwen3:4b-instruct-2507-q4_K_M`); backup `PLANNER_BACKUP_MODEL`. JSON schema passed as `format` (`docs/prompts.md`).

## Who owns what (commit only in your own area)
| Area | Owner |
|---|---|
| `backend/` | Satwik |
| `web/` (incl. `web/render/render.mjs`) | Varun |
| `data/` | Varun (fallback lesson content: both review) |
| `docs/`, `AGENTS.md` | Both. Change contracts only together. |

## Layout
```
backend/app/
  main.py            FastAPI app: routes, /media static, serves web/dist
  config.py          settings from .env (the only place that reads env vars)
  jobs.py            job queue, one worker thread, stage runner, timings + peak RAM
  cache.py           content-addressed cache + cache/index.json
  planner/           ollama_client.py, prompt.py, lesson.schema.json, schema.py, validate.py, fallback.py
  localize/          translate.py (IndicTrans2), terms.py (term masking)
  speech/            engines.py (registry), kokoro_engine.py, parler_engine.py, textnorm.py, audio.py
  timeline/          build.py, captions.py, srt.py
  export/            render.py (calls Node renderer), ffmpeg.py (faststart, ffprobe)
web/src/
  app/               pages: input, progress, player (+ edit, library later)
  lesson/            Lesson.tsx, types.ts, theme.ts, fonts.ts, timing.ts
  lesson/scenes/     TitleCard, CodeWalkthrough, Diagram, Formula, Recap (Quiz later)
  lesson/chrome/     StepHeading, CaptionBar, ProgressBar
  remotion/          index.ts + Root.tsx (registers composition "Lesson")
web/render/render.mjs   Node: selectComposition + renderMedia → MP4
data/fallback/       python_loop.en.json (the built-in fallback lesson)
data/samples/        sample lessons, mock timelines, render props for building the renderer
```

## Contracts (never change silently)
- **Lesson JSON v1:** `docs/lesson-schema.md` §2–5. Python: `backend/app/planner/schema.py`. TypeScript: `web/src/lesson/types.ts`. Keep the two identical.
- **Timeline v1 and render props:** `docs/lesson-schema.md` §6–7.
- **API:** `docs/api-contracts.md`.
- **Render CLI:** `node web/render/render.mjs --props <file.json> --out <file.mp4> [--concurrency N]`. Prints one JSON object per line: `{"progress":0.42}` while rendering, then `{"done":true,"out":"<path>","ms":51234}` or `{"error":"<message>"}`. Exit code 0 on success, 1 on failure.

## Rules for scene code (`web/src/lesson/`)
- Components are pure functions of props + `useCurrentFrame()`. **No CSS animations or transitions, no `setTimeout`, no `Date.now()`, no `Math.random()`.** Remotion renders frames out of order in parallel tabs.
- Animate with `interpolate()` / `spring()` and always clamp (`extrapolateLeft: 'clamp', extrapolateRight: 'clamp'`).
- Inside a `<Sequence>`, `useCurrentFrame()` counts from the sequence start. Timeline frames are absolute, so use `rel = beat.start_frame - scene.start_frame`.
- Text must fit the 1280×720 frame: clamp lines and shrink the font by length. Nothing may overflow.
- Every text element gets `lang={language}` and the script's font family from `fonts.ts`.
- Load fonts with `@remotion/fonts` `loadFont()` + `staticFile()`. Never `@import` from the web.
- Audio is one `<Audio>` for the whole lesson (`timeline.audio`). If it is `null` (mock timeline), render silently.

## Backend rules
- Each stage is a function `run_<stage>(ctx) -> ctx` in its own module. The job runner times it (ms) and records peak RSS. Stages never call each other.
- One worker thread runs one job at a time (models are heavy).
- Cache everything content-addressed (`docs/pipeline.md` §8) and never regenerate what's cached.
- Failure in plan or validate → the fallback lesson. Failure later → the pre-rendered fallback package for that language. Always return something playable and set `fallback: true` with a reason.
- Log one JSON line per stage to `cache/runs.jsonl`: `{job_id, stage, ms, rss_mb, device, ok, note}`.

## Commands
```
# backend (repo root, venv active: & C:\Users\ROG\Kavach\kavach-env\Scripts\Activate.ps1)
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# web dev (Vite on 5173; proxy /api and /media to 8000)
cd web && npm run dev

# scene work with mock props
cd web && npx remotion studio

# demo build: backend serves web/dist; renderer uses web/build
cd web && npm run build && npx remotion bundle

# render by hand
node web/render/render.mjs --props data/samples/python_loop.props.json --out cache/test.mp4
```

## Conventions
- Python: type hints, `pathlib.Path`, Pydantic models at every boundary, config only via `config.py`.
- TypeScript: strict mode, no `any` in lesson types, one file per scene type.
- Windows: build paths with `pathlib` / `path.join`. Never hard-code `/` or `\`.
- Small commits, message = what + why. Pull before every push. Never commit `.env`, `cache/`, `models/`, `node_modules/`, `web/dist/`, `web/build/`.

## Definition of done (from the problem statement)
1. Topic, level, language and length reach the backend.
2. Planner output passes the schema check. A bad response falls back to the built-in sample lesson.
3. The player plays a title card, a diagram (labels + arrows) and a code walkthrough, with play, pause, next scene and replay.
4. The same lesson plays in English, Hindi and Kannada with audio, captions (right script) and scenes in sync.
5. A playable 1280×720 H.264/AAC MP4 of the full lesson, plus an `.srt`.
