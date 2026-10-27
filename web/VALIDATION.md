# Frontend validation

## Verified in this environment

- Strict TypeScript typecheck and Vite production build. Vite reports nonblocking
  bundle-size and dependency `use client` directive warnings.
- 35 unit tests: timing, all 15 diagram/count combinations, code highlighting,
  output persistence/backward scrubbing, inert tokenization, formula segments,
  runtime props validation, SRT Unicode/timestamps, API paths/errors, cancellation.
- 62 representative sample-frame checks in Chromium: captions, scene offsets,
  step order, silence, chrome geometry, and local script fonts.
- Rendered stills of all 12 sample scenes; timeline metadata and same-frame PNG
  determinism checked after rendering other scenes.
- Studio launched separately with each sample's props and verified the correct
  title card for each lesson; all scene types also exercised in Player/renderer.
- Diagram beginning/middle/end screenshots, all three layouts with 2–6 nodes,
  cycle closing arrows, and out-of-order code/output scrubbing.
- Long Hindi/Kannada text probes across all three lessons, preserving displayed
  code. These are font/layout probes, not real translations.
- Desktop and 390px mobile layouts with no horizontal overflow; sample playback,
  previous/next/replay, CC, SRT download, and input validation.
- Contract-fixture workflow: one submission, 500 ms nonoverlapping polling,
  playback before MP4 readiness, final media refresh, reload, cached/fallback
  jobs, 404/422/500/network/job errors, and cleanup on navigation/completion.
- A frame update under Chromium 4× CPU throttling; not a full phone playback or
  subjective stutter assessment.
- No external lesson-app requests. Studio playback checked with its external
  development-tool update/bug requests blocked.
- Full Python-loop MP4: 67.8 seconds, H.264, 1280×720, 30 fps, yuv420p, BT.709.
  Silent because mock audio is null. Export stdout parsed as JSON lines; CLI
  argument errors return one JSON error and exit 1. Matching SRT derives from
  the same timeline captions. Outputs: `cache/test.mp4` and `cache/test.srt`.

## Unverified prerequisites

The actual `http://127.0.0.1:8000/api/health` connection was refused, and this
checkout has no `backend/`. Real topic generation, real stage/RAM measurements,
translated lesson quality, narration synchronization, AAC with Satwik's WAV,
live MP4/SRT downloads, and backend faststart checks remain unverified.
Contract fixtures are test-only and do not establish real backend success.

No real phone, native-speaker listening review, offline AI model run, 20-topic
backend run, or live CPU-only AI benchmark was available. Browser checks do not
substitute for these. No backend or schema contracts were changed, and no fake
audio or AI-generated lessons were created.
