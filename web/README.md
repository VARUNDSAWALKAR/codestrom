# Frontend and lesson renderer

From `web/`:

```sh
npm ci
npm run typecheck
npm test
npm run build
npm run studio
```

Use Node 24. `npm run dev` runs the student-facing application on port 5173.
Remotion Studio runs on port 3000 and registers `Lesson` with the Python loop
sample. All five scene types are implemented. Browser playback and MP4 export
use the same `RenderProps` and composition; all durations come from the timeline.

`npm run build:demo` builds Vite `dist/` and Remotion `build/`. Rebundle after
changing lesson code. From the repository root:

```sh
node web/render/render.mjs --props data/samples/python_loop.props.json --out cache/test.mp4 --concurrency 2
```

The exporter emits JSON lines, exits 1 on error, and uses preinstalled Chromium.
Set `REMOTION_BROWSER_EXECUTABLE` or `CHROMIUM_PATH` for a custom location. It
never downloads a browser at runtime. H.264, 1280×720, 30 fps, CRF 23, yuv420p,
BT.709; optional narration uses AAC at 128 kbps. Mock audio remains silent.

`src/remotion/sampleProps.ts` is the typed copy of
`data/samples/python_loop.props.json`. The tests detect drift between the two.
Tests also check all three samples' scene boundaries, beats, captions, and step
states, including frame conversion inside Sequences.

With Vite and Studio running, `npm run test:browser` checks representative frames
of all three samples, chrome geometry, captions, and local Hindi/Kannada fonts.
`npm run test:render` bundles the composition, verifies metadata for each sample,
and renders a still from every scene. Both use local Chromium; set
`CHROMIUM_PATH` if it is not at `/usr/bin/chromium`. Artifacts are ignored under
`.validation/`. Studio's own development UI may probe Remotion's external update
and bug service; the browser test blocks external Studio requests and verifies
that the composition still opens. The lesson application makes no such requests.

`npm run test:edges` checks out-of-order scrubbing, rendered code/output state,
diagram start/middle/end frames, 2–6 nodes per layout, and long Hindi/Kannada text
across all samples. `npm run test:app` checks desktop/mobile UI and API contract
fixtures; these fixtures never replace the real backend in application code.
`npm run test:render` also compares identical PNGs after revisiting a frame.
With port 3000 free, `npm run test:studio` launches Studio sequentially with
each sample's `--props` input and verifies the correct lesson opens.

Noto fonts and OFL license files are bundled in `public/fonts/`. The postinstall
script refreshes them from the locked Fontsource packages; application code only
loads same-origin local files. Only the selected language's script plus Latin
and mono are loaded. No audio file is expected for the mock timelines; `audio:
null` renders silently. A non-null timeline selects `web` or `wav` and prefixes
its path with `mediaBase`.

The app fetches health/config and uses available backend settings. Job polling
runs every 500 ms, stops on done/error/navigation, and has a 12-minute bound.
Requests time out after 10 seconds. Retry checks the same job without resubmitting.
The player opens when playable; media is refreshed again when export finishes.
Hash routes support job and lesson reloads. Downloads are enabled only when
real media paths are supplied. SRT can also be derived locally from captions.

Without the local backend on port 8000, generation is disabled and clearly
labelled sample previews remain available. No fake success is shown. Real
integration and narration checks still need Satwik's backend and audio; see
`VALIDATION.md`. No Quiz, scene editor, revoicing, library, or capture exporter
was added. Backend and lesson-schema contracts are unchanged.
