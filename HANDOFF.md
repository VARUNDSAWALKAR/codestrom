> Historical frontend-only handoff from Varun. Backend Tasks 1-3 are now
> consolidated in this checkout; see [README.md](README.md) and
> [Gate 1 validation](docs/gate1-validation.md) for current status.

# Blu VisualTeacher — collaborator handoff

This handoff contains the current frontend implementation. Read `AGENTS.md`, `CLAUDE.md`, and
the relevant documents under `docs/` before making changes.

## What you receive

- `web/src/app/`: responsive lesson creator, progress UI, custom Player controls,
  sample previews, and the typed FastAPI client.
- `web/src/lesson/`: all five scene components, captions, theme, fonts, timeline
  helpers, and runtime render-props checks.
- `web/src/remotion/`: composition registration and the initial Python sample.
- `web/render/render.mjs`: MP4 CLI used by the backend integration contract.
- `web/public/fonts/`: local Noto fonts and their licence notices.
- `data/`: original lesson schema, fallback, and all sample JSON inputs.
- `docs/`: architecture, API, lesson, scene, export, and licence contracts.
- `web/tests/` and `web/scripts/`: unit, browser, layout, app-contract, Studio,
  and rendering checks.
- In the shared ZIP, `demo/python_loop.mp4` and `demo/python_loop.srt` are real
  outputs from the supplied mock timeline. The video is deliberately silent.
- `MANIFEST.sha256` in the ZIP lists hashes for the packaged files.

The backend, AI models, credentials, Git history, `node_modules`, build outputs,
and test screenshot caches are not included. Satwik owns `backend/`; coordinate
with him rather than changing its contract or inventing backend responses.

## First run

1. Extract the entire `blu-visualteacher` folder. Keep `web/`, `data/`, and `docs/`
   together; source imports and tests use this layout.
2. Install Node.js 24 (includes npm). For MP4 export, install Chrome or Chromium
   locally. FFmpeg/ffprobe are useful for checking output; the browser is not
   downloaded automatically by the exporter.
3. Open a terminal in the extracted `blu-visualteacher/web` folder:

   ```sh
   npm ci
   npm run dev
   ```

   Dependency installation needs npm registry access once. Fonts are already
   bundled locally and refreshed by postinstall. No online font or AI service
   is required for sample playback. Open the local address printed by Vite.
4. Select a sample lesson. The three samples work without a backend. Live
   generation stays disabled until the real backend is available.
5. In a second terminal in `web/`, run `npm run studio` for animation work.

## Render the sample video

From the extracted project root (one directory above `web/`):

```sh
node web/render/render.mjs --props data/samples/python_loop.props.json --out cache/test.mp4 --concurrency 2
```

The CLI discovers common local Chromium paths. If needed, set
`REMOTION_BROWSER_EXECUTABLE` or `CHROMIUM_PATH` to the executable path.
Windows PowerShell example, for a standard Chrome installation:

```powershell
$env:CHROMIUM_PATH = "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
```

On macOS, Chrome is usually at
`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.
Browser test scripts also use `CHROMIUM_PATH`; their default is Linux Chromium.

## Build and test

From `web/`:

```sh
npm run typecheck
npm test
npm run build:demo
```

With Vite and Studio running, use `npm run test:browser`, `npm run test:edges`,
and `npm run test:app`. `npm run test:render` independently renders sample
stills. `npm run test:studio` requires port 3000 free and starts/stops its own
Studio instances. Rebuild the Remotion bundle after changing lesson components.

## Continue collaboration

The frontend uses same-origin `/api` and `/media` paths. Vite proxies them to
Satwik's local backend on port 8000. The exact endpoint shapes, job stages, and
media readiness rules are in `docs/api-contracts.md`. No tokens or secrets are
needed for local sample work.

Already checked: 35 unit tests, desktop/mobile controls, 62 sample-frame checks,
all diagram layouts/counts, long Hindi/Kannada layout probes, deterministic
rendering, and the silent 67.8-second H.264/yuv420p sample video. Detailed limits
are in `web/VALIDATION.md`.

Next joint checks require the actual backend and real narration: generate an
English lesson, check real Hindi/Kannada translation and audio sync, render a
real WAV to AAC, verify downloads and faststart, and test on a physical phone.
The contract-fixture tests do not establish that those live operations work.

Git history is intentionally absent. To contribute back to the shared project,
use your team's repository and branch workflow, compare these files against the
latest shared branch, and preserve any work your teammate has already added.
