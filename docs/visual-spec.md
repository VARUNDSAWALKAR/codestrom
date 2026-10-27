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
