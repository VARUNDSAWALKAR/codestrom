# VQ3 minimum narrated visual integration - 28 October 2026

Completed: one verified narrated visual demo. Scope: explicit authored English
array content, not automatic
topic-to-visual generation. VQ1/VQ1.1/VQ1.2 model planning remains disabled.

Verified VQ2 and incoming changes were protected before editing by a source-only
ZIP, per-file SHA-256 manifest and staged/unstaged patches:
`C:\Users\ROG\AppData\Local\Temp\blu-vq3-checkpoint-2685013b-b12c-4f27-b95c-95654203f3fd`.
30 source/test/fixture/doc files were verified from the ZIP. No secrets/media/cache.
The isolated worktree remains at 97e1116 with pending merge 95c2408, uncommitted.

The existing cached Binary Search worked example narrates checking 8, contradicting
the reviewed array values and found-7 state. It is not reused or silently repaired.
The controlled demo derives a new isolated hex cache identity from the unchanged
authored sample source (the cache requires hex IDs). Only lesson_id and the
corresponding spec identity/source fingerprint change in that derivative; the
original fixture and all production plan IDs remain unchanged.

Implementation checkpoint: optional render-props visualSpec; explicit ExportContext
injection with canonical validation; normal Lesson/VisualSpecRenderer routing;
fresh bundle only for visual-bearing export; no default job/API injection.
Legacy JSON serialization/cache digests remain unchanged when visualSpec is absent.

Initial checkpoint (before verification): no real TTS/export was run before the
focused checks passed. The controlled command
uses existing run_voice/run_timeline/run_export in its own output/cache and local
media server; exact audio keys may be copied read-only before generating missing
beats. Models, prompts, language approvals and production caches are unchanged.

Pre-inference checkpoint: 67 frontend tests passed; TypeScript/Vite build passed.
Focused backend narration/timeline/export/visual tests: 219 passed, 1 skipped in
37.26 seconds (existing renderer-presence skip). Local Kokoro assets and renderer
exist. Eight source narration beats are required; isolated sample ID ef7f9a8338d3.
Proceeding to one real controlled Kokoro/timeline/MP4 run, with exact-key cache
reuse attempted first and no Ollama/translation calls.

## Final controlled acceptance

MP4: original checkout
`scratch/vq3-narrated/ff927c5c-fce6-4e95-b0e9-6418ba6183cf/lesson.mp4`.
666,621 bytes; H.264, 1280x720, 30 fps, 737 frames / 24.566667 seconds video;
AAC stereo 48 kHz, 24.576 seconds audio. Full decoding passed. This short authored
demo does not establish the full 30-90 second production lesson acceptance range.
Its target_seconds metadata is retained from the authored source; actual duration
comes entirely from recorded PCM and existing pause scheduling, not invented time.

The unchanged authored source text/scenes are reused with new isolated sample
ID ef7f9a8338d3 solely to satisfy the cache's hex-ID path contract. The sidecar's
lesson_id and source_fingerprint are recomputed for that sample, validated and
bound to its measured timeline. No cached production plan was modified. Cached
Binary Search was rejected as incompatible because of its narrated check-8 error.

Stages: real Kokoro voice 7.022 s (8 new beats, 0 exact cached hits, 20.623 s speech),
timeline 1.261 s (737 frames, tempo 1), normal production export 62.892 s.
No Ollama/translation inference. No model/voice configuration was changed.

| Action | Recorded beat | Bound absolute frames | Inspected before/mid/after |
| --- | --- | --- | --- |
| Reveal 1 | s2.step0 | 262..300.4 | 261 / 281 / 302 |
| Highlight midpoint 5 | s2.step1 | 333..366 | 332 / 349 / 367 |
| Reveal interval 7,9 | s2.step2 | 395..444.2 | 394 / 419 / 446 |
| Highlight found 7 | s2.step3 | 485..513.8 | 484 / 499 / 515 |

The normal Lesson composition, not the standalone VQ2 demo composition, renders
the MP4. Title and recap remain legacy. Actual decoded frames show the ordered
array, intermediate linear emphasis, held final state, candidate outline and
found value without covering captions. Browser Player uses the same normal
Lesson path and passed all 14 caption/object/state samples, including title/recap.
Decoded MP4 versus browser mean RGB error is 0.91-1.24/255 across these samples,
consistent with H.264/color conversion; visual inspection passed. Exact pixel
equality is not claimed for compressed MP4. Backwards browser seeking is identical.

Audio is non-silent (source RMS 0.09162), full audio/video decoding passes, and
decoded AAC/source WAV correlation is 0.9999238 at zero lag. All eight measured
clip lengths match their beat durations within one frame of rounding. Eight SRT
captions exactly match timeline serialization and observed browser captions.
This is beat/chunk synchronization, not new word-level forced alignment or human
pronunciation approval.

Missing, invalid-version and unsupported-layout sidecars visibly render trusted
legacy diagrams in the normal browser. Normal Remotion stills also verify an
absent sidecar and the existing Water Cycle legacy sample. No second full video
or inference run was needed. Existing videos/caches were preserved, not regenerated.

## Files and regression

- backend/app/timeline/schema.py: optional visualSpec, absent-field serialization.
- backend/app/export/render.py: explicit validated sidecar injection/fallback.
- backend/render_visual_demo.py: isolated authored real-narration/export command.
- backend/tests/test_vq3.py: mocked validation/cache/production-isolation checks.
- web/src/lesson/types.ts, Lesson.tsx: optional sidecar normal scene selection.
- web/src/lesson/visual/VisualSpecRenderer.tsx: backend/internal dispatch.
- web/src/lesson/visual/BackendArrayScene.tsx: usage comment only; verified engine unchanged.
- web/render/render.mjs: fresh source bundle for visual-bearing exports.
- web/tests/all.ts, backend-array.test.ts, vq3.test.ts: test registration/coverage.
- web/scripts/verify-narrated-visual.mjs: real export/browser/media inspection.
- docs/lesson-schema.md, frontend-integration.md, visual-spec.md, this checkpoint.

Frontend: 67 passed, typecheck/build passed. Focused backend runs: 219 passed,
1 skipped plus 41 passed / 13 subtests passed (260 distinct tests total). The
complete backend suite was not run: targeted checks covered narration, timeline,
export, sidecar validation, production pipeline and canonical language identity.
Existing Vite module-directive/chunk-size warnings remain. No source/runtime
tests failed in the final checks. Unstaged diff --check passes.

## MVP verdict and limits

Verified controlled narrated visual demo; **not automatic topic-to-visual
generation**. Ready for final owner/UI-driven acceptance of this controlled
artifact and optional render path. The ordinary Create-topic flow does not
select this fixture; that flow and arbitrary-topic semantic quality are not
accepted by this result. No authored substitution for unrelated topics occurs.

Only English array_grid rectangle/text/highlight_region and reveal/highlight
are supported. Other objects/layouts/actions and Indic specialized visuals use
legacy. Full renderer-build-aware media invalidation remains future work; this
slice includes the full sidecar in media identity and bypasses stale prebuilt
bundles when it actually renders. Automatic planners remain disabled, and
existing language approvals, models, planner prompt, Lesson/Timeline schemas,
production IDs, caches and original worktree are unchanged.

The media/QA servers owned by this run were closed. No commit, push or additional
merge was performed. The source checkpoint and all raw acceptance/verification
artifacts are preserved. Stop after this one video.
