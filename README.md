# Blu VisualTeacher

Local animated lessons built with React, TypeScript and Remotion. The website
and MP4 exporter use the same JSON-driven `Lesson` composition.

Implemented: title cards, code walkthroughs, flow/cycle/labelled diagrams,
formulas, recaps, captions, local Noto fonts, a responsive lesson creator/player,
and the typed frontend client for the documented FastAPI endpoints.

Requires Node 24 and local Chromium for rendering. Dependencies are pinned in
`web/package-lock.json`. This checkout now includes backend Tasks 1-3: FastAPI foundation, local Kokoro
narration/timeline/captions, and Remotion export orchestration. The three supplied
silent samples still work independently. API and lesson-schema contracts are unchanged.

## Preview

![Blu VisualTeacher website](docs/previews/website.png)

[Mobile preview](docs/previews/mobile.png) · [Code walkthrough preview](docs/previews/code-walkthrough.png)

These are screenshots of the running frontend. Samples have mock timing and
no narration; live generation requires the local backend.

## Run locally

```sh
cd web
npm ci
npm run dev
# In another terminal, from web/:
npm run studio
```

The backend serves health/config, local media and the built website on port 8000.
Vite proxies `/api` and `/media` to it. Topic generation and job polling endpoints
are not implemented yet; Gate 1 uses the CLI workflow below. The UI still
clearly separates samples from live generation.

Build the website and renderer with `cd web && npm run build:demo`.
Render from the repository root:

```sh
node web/render/render.mjs --props data/samples/python_loop.props.json --out cache/test.mp4 --concurrency 2
```

The exporter emits JSON lines and derives timing from the timeline. It never
downloads a browser at runtime. Set `REMOTION_BROWSER_EXECUTABLE` or
`CHROMIUM_PATH` if auto-discovery does not find your preinstalled browser.
The mock timelines render silently. Real narration uses local media paths and
`audioVariant: "wav"`. Rebundle after changing lesson components.

See [web/README.md](web/README.md) for commands and
[web/VALIDATION.md](web/VALIDATION.md) for evidence and remaining live checks.
Project contracts and licences are under [docs/](docs/README.md).

## Gate 1: narrated MP4 from the integrated checkout

See [docs/gate1-validation.md](docs/gate1-validation.md) for verification evidence,
current limitations and the consolidation inventory. `HANDOFF.md` and
`web/VALIDATION.md` retain Varun's original frontend handoff context.

Use Python 3.11 with the existing dependencies in `backend/requirements.txt`;
`backend/constraints.txt` keeps transformers at 4.46.1. On this machine use
`C:/Users/ROG/Kavach/kavach-env/Scripts/python.exe`. No environment or model weights
are stored in the repository. `.env.example` documents the local configuration;
copy it to `.env` only if overrides are needed. Keep models at local paths.
FFmpeg, ffprobe, Node 24 and Chrome/Chromium must already be installed.

From the repository root in PowerShell (after building `web/` as above):

```powershell
$python = 'C:/Users/ROG/Kavach/kavach-env/Scripts/python.exe'
& $python -m backend.generate_narration
& $python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Keep the server running. In another terminal at the repository root:

```powershell
$python = 'C:/Users/ROG/Kavach/kavach-env/Scripts/python.exe'
& $python -m backend.export_lesson
& $python -m pytest backend/tests -q -ra
```

The real narrated output is `cache/lessons/fallback-python-loop/en-female-1/lesson.mp4`,
with `lesson.srt` alongside it. Both are generated locally and ignored by Git.
The backend must serve this checkout's cache for the renderer to fetch its WAV.
No Ollama planning or Kannada generation is included in Gate 1.
