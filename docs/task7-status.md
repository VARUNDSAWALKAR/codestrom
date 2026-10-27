# Task 7 — Kannada voice integration

## Scope and safety

Started 27 October 2026 in `C:\Users\ROG\VisualTeacher-varun`, `main` at
`03bece6ae9308a98340af78f801d8d734de8b7b3`. No Git mutation authorized.
The whole task split was read: it is an hour-by-hour schedule with no numbered
Task 7. H+10-12 explicitly schedules Parler engine, language/profile/voice routing,
voice choice/speed, Indic font/caption checks and synchronized hi/kn MP4s.
This is substantively the requested voice milestone. The explicit Task 7 prompt
authorizes CPU Parler feasibility and integration, superseding the old GPU-only
planning assumption. No Task 8/9 or VQ1 scope is taken on.

Pre-existing modifications preserved: config, lessons_api, localize/__init__, main,
orchestrator, pipeline_ops, foundation/task5b tests, api-contracts, frontend docs,
narration-languages, task5-status, test-log, App.tsx and CreateForm.tsx. Existing
untracked work: language_policy, localize/model/terms/translate, localization CLI,
Task 6 identity/localize/pipeline tests, localized fixtures, task6-status.
Existing caches/review packs are preserved; no frontend changes permitted.

## M0 — complete

- Baseline using specified Python, CPU/offline env and bytecode disabled:
  **197 passed, 1 skipped, 42 subtests passed in 44.39 s**. Skip remains
  test_task3.py:118 (real renderer exists). No pytest warnings.
- Kannada localized fixtures and canonical en/hi/kn identity tests passed as part
  of that suite. Current plan identity and localization cache interfaces reused.
- Hindi human approval dated 27 October 2026 exists in task6-status. Production
  `.env` remains `APPROVED_LANGUAGES=en,hi`; Kannada is not approved or enabled.
- Read-only font check: local Noto Sans Kannada 400/500/600 files exist and are
  mapped by fonts.ts. Existing web/build and web/dist exist. Frontend App/CreateForm
  SHA-256 values match previous checkpoints.
- Reviewed AGENTS, full task split, Task 6 checkpoint, narration/pipeline/schema,
  API/frontend contracts, test cases/log and licences; speech/localization/config,
  approval, production ops, orchestration, audio cache and timeline/export interfaces.
- Prior experiment summary identifies AI4Bharat Indic Parler-TTS, revision
  `660bc53c64ae83150613264111708a0465211237`, local 3,751,321,772-byte safetensors,
  separate local FLAN-T5 description tokenizer. Model card lists Kannada and
  recommends Suresh/Anu. Apache-2.0 model and FLAN-T5 tokenizer are already licensed.
- Prior experiments used torch 2.11.0+cu128, transformers 4.46.1, parler-tts 0.2.2,
  CPU float32/4 threads, 44,100 Hz. Seven speaker/seed variants succeeded; prior
  RTF about 3.48-4.30 with 6.2-6.6 GiB process RSS. These are background evidence,
  not fresh feasibility or native-speaker quality approval.

## M1 — feasibility complete

Fresh local-only CPU float32 load succeeded in **6.258 s**; 4 threads, installed
torch 2.11.0+cu128 / transformers 4.46.1 / parler-tts 0.2.2. Separate local prompt
and FLAN-T5 description tokenizers loaded without remote lookup. Network audit
recorded no attempted connections. No dependency/model change or substitution.

| Sample | Speaker | Inference s | Audio s | RTF | Rate | RMS / peak |
|---|---|---:|---:|---:|---:|---|
| Suggested Kannada sentence | Anu | 27.719 | 6.293 | 4.405 | 44100 | 0.05958 / 0.33054 |
| Python/range(3)/0,1,2 | Suresh | 18.503 | 4.807 | 3.849 | 44100 | 0.07833 / 0.49573 |

Sampled peak RSS **6826.62 MiB**, load sample 4260.37 MiB. Both arrays/WAVs
finite, nonempty, non-silent and below generation cap. Actual console warnings:
optional Flash Attention 2 absent; component-config replacement information;
internal decoder attention-mask warning despite explicit description/prompt masks.
No traceback. Outputs/results preserved in `scratch/task7/feasibility/`.
These checks establish local CPU feasibility, not Kannada intelligibility or
pronunciation approval. Model card recommends distinct Anu/Suresh named voices;
the legacy gender options will map to those names explicitly, not one shared voice.

## M2 — adapter complete

Added `speech/parler_engine.py`, `speech/kannada.py`, `speech/kn_textnorm.py`.
Lazy, serialized model initialization/inference/release; local-only model plus
separate local description tokenizer; CPU float32, configurable device/threads.
Named legacy voice mapping: female→Anu, male→Suresh, both recommended in the local
model card and independently exercised in previous experiments/fresh feasibility.
No guarantee of perceived gender/pronunciation quality before native review.
Unknown speakers/languages/speeds are rejected. Speech speed uses deterministic
FFmpeg atempo after moderate-pace generation, not an unmeasured prompt hint.
Raw 44.1 kHz is processed into validated 24 kHz mono PCM16 for the existing timeline.
Potential generation-cap truncation is an error, never silent shortened output.
Speech-only cleanup reuses established markup normalization; Latin technical
terms stay verbatim. No invented phonetic rewrites; normalization is versioned.

## M3 — integration complete

Minimal dispatch in `run_voice`: Kannada uses its independent adapter; original
Kokoro implementation/body remains intact for en/hi. `NarrationContext` accepts
either engine. Production ops select Parler only for kn and preserve typed errors.
Canonical key logic, planner, localizer, timeline and exporter internals unchanged.
Stage order unchanged; scene/beat IDs and original narration/captions retained.
Audio cache uses existing audio_key convention with Kannada/Parler namespace,
canonical lesson ID, original/normalized narration, speaker, speed, asset/package/
generation/normalization version. WAV+provenance/hash records validate before hits;
corrupt files fail explicitly without deletion or silent regeneration.
LOW_RAM releases after clip cache publication and waits for active model sessions.

## M4 — approval/health complete

Production `.env` remains en,hi; Hindi human approval is preserved. Kannada is now
technically eligible only when the user separately approves kn and enables Parler.
Default code approval still en. Shared precheck/config policy excludes kn when
ENABLE_PARLER=0. Existing tts_parler health now supports CPU: enabled is capability,
ready is successful resident initialization; import/en requests do not load Parler.
No automatic Kannada approval or frontend changes.

## M5 — mocked coverage complete

Focused Task 7 + Task 6 pipeline/identity + Task 5B + Task 2 tests:
**90 passed, 13 subtests passed in 5.16 s**. Covers routing, offline loader calls,
lazy/concurrent init/release, valid PCM, silent/corrupt files, speaker choices,
mixed-script normalization/Unicode, cache namespace/model/voice/speed/ID isolation,
cached canonical plan/translation (guarded against fresh HTTP/inference), real
timeline/caption/HTTP preview, approval/config/health and structured synthesis errors.

Initial focused run: **89 passed, 1 failed, 13 subtests in 118.26 s**. Failure
was the mock integration's 5-second helper deadline: every synthetic 44.1 kHz
beat unnecessarily spawned FFmpeg for resampling. Test tones now use native
24 kHz for cache/integration checks (real 44.1→24 kHz processing is covered
separately), and synthetic voice + real timeline uses a 15-second deadline.
No real full lesson was attempted before this test correction.
The faster follow-up surfaced an additional fixture issue: 100 ms tones provide
only three frames, fewer than long Kannada caption chunks require. The integration
fixture now uses two-second synthetic beats; no production duration was hard-coded.
Finally HTTP SRT comparison normalizes CRLF/LF while checking all cue text/times.

## M6 — real Kannada preview complete (one primary attempt)

Job `j_47e52c6ae18e`, canonical Water Cycle `c1f63f0ed69b`, kn-female-1,
beginner/science/60 s/speed 1.0/Anu. Canonical English plan and Kannada translation
were validated cache hits under guards: **zero Ollama calls and zero translator
inference**. Kannada approval was confined to isolated test settings; production
`.env` is byte-identical (en,hi). No full-lesson retry needed.

Real Parler cold load **7.150 s**; primary preview wall **271.060 s**. Sampled
process peak **6785.49 MiB**. Output **72.7 s**, 24 kHz mono PCM16, RMS **0.09257**,
peak **0.89127**, **2181 frames at 30 fps**, tempo **1.0**, **17 captions**.
Eleven beats retain IDs/order/original Kannada narration; one clip reused within
the job. SRT matches timeline cues; concatenated caption chunks match each beat.
All audio/SRT/timeline/props/lesson HTTP URLs returned 200/nonempty. Preview ready
before explicitly skipped export; MP4 null and absent. Parler health ready true
after real load. Model explicitly released after the run before rendering.

Seven existing localized-note length warnings remain. No 90-second/tempo warning,
generation cap, model error or unexpected inference. Full stage timings, clips,
memory and media sizes: `scratch/task7/preview.json`. Technical preview is proven;
native-speaker quality and browser/MP4 visual checks are still separate.

## M7 — real Kannada MP4 complete (one primary attempt)

Existing renderer/exporter produced
`cache/lessons/c1f63f0ed69b/kn-female-1/lesson.mp4`, **1,942,066 bytes**.
Export **163,650 ms**, acceptance wall **173.903 s**. FFprobe: H.264 High,
1280x720, yuv420p, **30/1 fps**, **2181 frames**, video **72.700 s**; AAC LC,
48 kHz stereo, audio/container **72.704 s**, start times 0. Difference **0.004 s**.
MP4 box structure/props fingerprint/provenance checks and complete FFmpeg decode
passed. HTTP media Range returned **206**. Input WAV/M4A/lesson/timeline/SRT
remained byte-identical; no new TTS/planner/translation inference. Production
config still en,hi. Only the owned temporary localhost server was stopped.

Five representative PNGs preserved in `scratch/accept/kannada/`: title, first/last
steps in each diagram. Inspected all five: Kannada glyphs/ligatures are visible,
no missing-glyph boxes or obvious clipping; headings, caption bands and notes
fit in the sampled frames. Expected captions match the timeline at those frames;
step highlights/arrows correspond to the sampled beat. Technical labels stay
English by keep_terms design. Native pronunciation/readability/perceptual sync
review is still required; no phone/browser-control acceptance is claimed.

Existing source-content defect remains: scene s2 is headed “Title Card” (translated
into Kannada), and diagram steps repeat across scenes. This was present in Task 5C;
it is a planner/content-quality follow-up, not a font/render failure or Task 7 fix.
No blocking frontend defect/handoff found in the representative frames. No retry
or web edit was needed. Full FFprobe/stage/frame report:
`scratch/accept/kannada/acceptance.json`.

## M8 — Kannada review pack complete, human approval pending

`scratch/review/kn/` contains exactly **20 English/Kannada pairs**, technical-term
examples/warnings/fractions in text_pairs.json, actual lesson.json, narration.wav,
lesson.srt, successful lesson.mp4, five screenshots, performance.json with preview/
export metrics, two short Anu/Suresh feasibility WAVs and unchecked CHECKLIST.md.
Known Task 6 fallbacks are explicitly included: Binary Search **two English labels**;
Python for loop **one English narration beat**. No false translated/approved claim.
Native reviewer must check meaning, pronunciation/naturalness, technical terms,
subtitle correctness, perceptual audio synchronization and full-video readability.
Pack creation copied existing artifacts only; no regeneration or extra render.

## M9 — final documentation/regression

Final focused Task 7 file: **23 passed in 3.75 s**. Full backend suite:
**220 passed, 1 skipped, 42 subtests passed in 47.66 s**. Only skip remains
test_task3.py:118; no pytest warnings. Updated CPU-Parler health and explicit
Kannada-approval expectations in two older tests; existing en/hi coverage retained.
Final extra coverage checks generation/normalization cache invalidation, actual
FFmpeg speed adjustment of synthetic audio, and LOW_RAM cleanup after failure.
No production code changes followed these tests; remaining edits are documentation.

Updated task7-status, narration-languages, API/frontend contracts, measured test
log and licence attribution. Corrected README's historical pre-API status and
pipeline's old GPU-only Kannada planning assumption; no new framework/dependency.
No `.env` change, no Hindi approval change, and no frontend source changes.
Final verification confirmed `.env` SHA-256 is unchanged, Hindi's dated approval
entry remains intact, production config advertises en/hi and rejects a kn POST
with 422 before any inference. Frontend App/CreateForm hashes match pre-task
values; Task 6 canonical/orchestrator/localizer file hashes match its final
checkpoint. Review pack completeness (20 pairs, five screenshots, real media,
known 2+1 fallback cases) passed. `git diff --check` passed; only routine Git
LF/CRLF notices. HEAD remains 03bece6; existing work is uncommitted and preserved.

### Task-owned source/test files

- Added `backend/app/speech/parler_engine.py`, `speech/kannada.py`,
  `speech/kn_textnorm.py`, `backend/tests/test_task7.py` (23 tests).
- Minimal edits to config, speech/engines, pipeline_ops, language_policy and main.
- Updated obsolete CPU health/Kannada approval expectations in
  test_foundation.py and test_task6_pipeline.py. No test was removed or skipped.
- Kokoro engine/textnorm, planner, localization, timeline, exporter and renderer
  implementations preserved. Canonical lesson IDs/hash remain unchanged.
- Prepared/retained scratch/task7/feasibility, preview.json;
  scratch/accept/kannada; scratch/review/kn; and Kannada variant/audio caches.

### Final outcome and next step

**M0-M9 technically complete; kn_technical_ready=true; Kannada human approval=false.**
One primary real lesson and one primary render succeeded; zero expensive retries.
Hindi approval and production `APPROVED_LANGUAGES=en,hi` are preserved.

Remaining limits: native Kannada pronunciation/meaning/perceptual-sync review;
seven note-length warnings (no clipping seen in sampled frames); historical generic
diagram/repeated-step/“Title Card” source-content defects; CUDA performance and
real-phone playback not tested. No blocking font/export issue found. No Task 8/9
project work or VQ1 started; no commit/push/tag/pull/reset/stash performed.

**Exact next step:** a Kannada-speaking reviewer uses
`scratch/review/kn/CHECKLIST.md`, text pairs and real WAV/SRT/MP4, then records
approval/corrections. Only after explicit separate approval may the owner set
`APPROVED_LANGUAGES=en,hi,kn` and restart. Task 7 does not enable Kannada itself.
