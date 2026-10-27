# VisualSpec contracts in the frontend

The proposed backend contract is `visual-v1`, defined on `feature/vq1-backend` by `backend/app/visuals/schema.py` and its exported JSON Schema. It remains separate from Lesson v1, Timeline v1, and production RenderProps while frontend feasibility is tested.

## Backend `visual-v1`

The exact TypeScript mirror is `web/src/types/visualSpec.ts`. The strict runtime boundary is `web/src/utils/parseVisualSpec.ts`.

- Geometry uses normalized content coordinates in `[0,1]`. The renderer maps them into the safe 1280×720 content area.
- Objects are rectangles, circles, ellipses, polygons, lines/arrows, typed paths, text, organizational groups, markers, highlight regions, particles, or closed-manifest assets.
- Relationships store topology and constraints separately from drawable connector objects.
- Scene layouts are `flow_cycle`, `spatial`, `array_grid`, `graph_network`, `coordinate_plane`, `comparison`, or `code_walkthrough`.
- Actions are `reveal`, `draw`, `move`, `highlight`, `transform`, or `trace`. Their `start` and `end` values are fractions of an existing narration beat.
- Legacy scenes have no specialized data and carry an explicit fallback reason.
- Unknown fields, invalid ranges, missing references, duplicate IDs, and actions tied to nonexistent source beats are rejected.

The three local authored fixture envelopes in `web/src/fixtures/data/` were copied unchanged from `backend/tests/fixtures/visuals/` on the feature branch. `web/src/fixtures/index.ts` validates and clones them, and can add a deterministic silent mock timeline for isolated frontend development. Production rendering must use the measured backend timeline.

## Renderer scene graph

`web/src/lesson/visual/` contains the renderer's internal pixel-space scene graph, now named `RenderVisualSpec`. It is compiled from the existing Lesson v1 diagrams and is not the backend `visual-v1` envelope. Keeping the names and boundaries distinct prevents the normalized backend contract from being passed directly to pixel-space primitives.

A later integration phase should compile a validated backend `VisualSpec` plus localized source labels and a measured timeline into `RenderVisualSpec`. It must not add VisualSpec silently to production RenderProps before both owners confirm that contract.

## Emergency authored array slice

`BackendArrayScene` is an explicit development-only sidecar renderer for the
unchanged `visual-v1` contract. It reuses the strict backend-contract parser,
then accepts only English `array_grid` scenes with rectangle/text/highlight_region
objects, ordered_with relationships and reveal/highlight actions. Unsupported
geometry, versions, references, overlapping/discontinuous channels or actions
route the whole selected scene to its trusted legacy Diagram. Groups are not
supported by this slice and are never expanded or drawn twice.

Positions are normalized centers in the handoff's safe rectangle. Source/literal
labels remain escaped text. Reveal opacity and semantic highlight colors use
clamped linear interpolation over each actual referenced beat fraction, with
held final states and pure backwards seeking. No fixed action duration is used.
The backend's complete source-aware validator remains authoritative; this
frontend subset is not a replacement for its fingerprint/scientific validation.

The genuine backend `array_grid_demo.json` is copied unchanged into fixtures.
`src/remotion/array-demo.tsx` is a separate QA composition; the production
Remotion root, Lesson, API and RenderProps are unchanged. Browser preview:
`/tests/array-demo.html` on local Vite. Its clock uses the existing silent fixture
timeline builder: this authored lesson has no measured narration recording.
Production integrations must supply their own measured localized timeline.

Run `node --import tsx scripts/verify-array-demo.mjs <new-artifacts-directory>`
for frame, browser, fallback and short silent clip checks with local Chrome.
This does not enable production visuals or automatic visual planning.

Verified 28 October 2026: 64 frontend tests passed, strict typecheck/Vite build
passed, and 166 backend VisualSpec compatibility tests passed. The actual
authored array scene was inspected at all four actions' before/middle/after
frames: ordered values, midpoint emphasis, right interval and found-value
emphasis are visible. Twelve browser screenshots are pixel-identical to the
corresponding Remotion PNGs; repeated out-of-order frame seeking is identical.
Invalid-version fallback visibly renders the original trusted diagram in both.

A 101-frame, 3.366667-second silent H.264 1280x720/30fps clip was fully decoded;
five decoded frame samples match the expected states within compression error.
Evidence: original checkout `scratch/vq2-array/9416e9c1-9a02-4273-9b99-7584cf05b40a/`.
This establishes one authored English array slice, not measured-audio, Indic,
other-layout or full-production acceptance. The pending merge remains
uncommitted. No production activation, schema change or automatic planning.

## VQ3 optional normal render path

Normal RenderProps now have additive optional `visualSpec`, separate from the
unchanged Lesson/Timeline/backend visual-v1 contracts. ExportContext accepts an
explicit sidecar, validates it against canonical English source, and drops invalid
data to legacy with a warning. Production jobs never select or inject one.
Missing fields serialize exactly as before, retaining legacy props hashes.
Lesson/VisualSpecRenderer dispatch valid supported arrays to the verified slice;
missing/invalid/unsupported scenes retain trusted legacy rendering. Visual-bearing
exports bundle current source instead of reusing a stale legacy-only bundle.

One controlled authored sample was rendered through existing real Kokoro,
sample-measured timeline/SRT and normal Remotion/FFmpeg export: 24.58-second
1280x720 H.264/AAC MP4. No automatic generation claim. See vq3-status.md for
identity, measured actions, frame/audio/browser evidence, tests and limitations.
