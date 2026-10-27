# VisualSpec v1 — frontend rendering boundary

VisualSpec is a renderer-owned, inert JSON format for VQ2. The current Lesson v1 backend does not emit it yet: `web/src/lesson/visual/adapters.ts` converts validated Lesson v1 diagrams into this format. A future backend field must be added to the Python schema and validated there before it reaches the renderer.

## Boundary

- `version` is `1`; the canvas is always `1280×720`.
- `language` uses the Lesson v1 language enum.
- `layout` is `spatial`, `flow`, `grid`, `network`, `coordinate`, `comparison`, or `code`.
- `primitives` is a tree of `rect`, `circle`, `ellipse`, `polygon`, `path`, `arrow`, `text`, and `group` objects.
- Primitive IDs are unique across the full tree. Unknown fields are rejected.
- Styling is inline and uses local colors only. URL paints and remote assets are rejected.
- VisualSpec is data. It never becomes HTML, code, a dynamic import, or an evaluated function.

## Timeline actions

Each action references an existing absolute-timeline `beat_id`. `offsetFrames` is relative to the beat start, and `durationFrames` controls only the visual transition, never scene or audio duration.

Supported actions:

- `reveal`: spring-based opacity and scale entrance.
- `draw`: path-length stroke tracing.
- `move`: interpolated x/y movement.
- `highlight`: a deterministic focus pulse.
- `transform`: interpolated translate, rotate, and scale values.
- `trace`: path tracing with an active color and glow.

`interpretVisualSpec` parses the JSON and rejects action or code-highlight references that do not match a real beat in the current `TimelineScene`. `VisualSpecRenderer` then converts Remotion's sequence-relative frame to the absolute timeline frame and resolves actions from that value. This keeps browser playback, backward scrubbing, out-of-order frame rendering, and MP4 export deterministic.

## Layout engine

`web/src/lesson/visual/layout.ts` precomputes educational geometry. It includes flow, grid/array, graph/network, coordinate-plane, and side-by-side comparison layouts. Existing code walkthroughs remain in `CodeWalkthrough.tsx`, where syntax tokenization and line highlights are already driven by timeline beats.
