# Task 6 status — offline localization

## Scope of the supplied implementation prompt

The initial prompt supplied on 2026-10-27 specified M0/M0b. The continuation
authorizes M1-M5; their current results are recorded first, with the original
M0/M0b checkpoint retained below as history. Hindi human approval remains pending.

Continuation now authorizes M1-M5. M0/M0b were verified in place, not repeated.
All original tracked/untracked changes are preserved. No new dependency/model
licences are needed: IndicTrans2 and its toolkit are already listed.

## M1 — localization package complete

Added `localize/terms.py`, `model.py`, `translate.py`, public API in `__init__.py`,
CLI `backend/localize_lesson.py`, `test_task6_localize.py`, and configuration for
the English-fallback ceiling (0.2) and CPU translation threads (4).
Protected spans, batched/deduplicated inference, script/restore retries,
SHA-256 model/plan/string provenance, checked atomic cache publication and
structured field diagnostics are implemented. Variant quality metadata is a
sidecar (`localization.json`); the Lesson/renderer schema is unchanged.

First mocked run: 34 passed, 1 failed across localization and identity tests.
The failing cache-hit test found a Pydantic defaults/fields_set comparison issue;
the structural comparison now normalizes defaults before comparing.
After correction, mocked localization plus M0b tests: **35 passed in 0.54 s**.
Covered restoration loss/duplication, verbatim unmasked recovery, script beam-5
retry/fallback, all six tags, unknown-field warnings, lengths, batching/dedupe,
cache checksum/provenance invalidation, interrupted publication, and release
waiting for the localization lock. These ran before any real translation calls.

## M2 — real translation complete (technical checks, not human approval)

T7 (`scratch/task6/t7.json`), ten documented cases each:
`<ID101>` hi **10/10**, kn **9/10**; `[T1]` hi **9/10**, kn **4/10**;
unmasked exact technical-term survival **0/10** in both languages. Unmasked
`range` became Hindi `सीमा` and Kannada `ವ್ಯಾಪ್ತಿ`. The failed Kannada ID case
transliterated `<ID101>` to `<ಐಡಿ101>`. Selected ID placeholders plus strict
validation/unmasked-once retry/verbatim-only acceptance; no style was 10/10 in
both languages, so never assume raw placeholder output is safe.

Three existing canonical plans (no new Ollama generation) translated into hi/kn.
Validated lesson fixtures and diagnostic sidecars saved in
`data/samples/localized/`; detailed measurements in `scratch/task6/m2.json`.

| Lesson | hi seconds / quality / English beats | kn seconds / quality / English beats |
|---|---|---|
| Water Cycle | 7.169 / complete / 0 of 11 | 3.348 / complete / 0 of 11 |
| Binary Search | 7.030 / complete / 0 of 11 | 7.140 / partial / 0 of 11 |
| Python for loop | 6.260 / complete / 0 of 9 | 6.178 / partial / 1 of 9 (0.1111) |

Binary Search kn retained two labels after two beam-5 script retries; Python kn
retained one narration after restoration/unmasked retry failed preservation.
All accepted translations passed >=70% target-script letters outside protected
spans; all protected spans remain verbatim, including code/indices/outputs.
Narration character expansion hi 1.20x, kn 1.25-1.38x; word expansion hi
1.30-1.50x, kn 0.87-0.93x. Every result's second call was a verified cache hit
with unchanged commit-marker bytes and no new model calls. Source plans remained
byte-identical. No Hindi approval or Kannada voice capability is implied.

## M3 — pipeline integration complete

Added `language_policy.py` and `APPROVED_LANGUAGES` (default en), shared by
production precheck and config availability. Only en/hi can be production-capable;
kn stays blocked even if listed. Added real localization bridge, quality ceiling
failure (`translate_incomplete`), operational failure (`translate_failed`),
diagnostic retention and lazy translator health. LOW_RAM release waits for model
users and runs only after localization cache/artifact publication. Existing
planner/TTS/timeline/export internals and M0b boundaries remain intact.

Focused mocked tests (M1/M0b/M3 + Task 5B): **68 passed, 13 subtests passed in
1.96 s**. Covered default and explicit approval, forced Kannada block, Hindi
voice-context identity and preview, unchanged cached English plan with no HTTP,
translation cache reuse, over-ceiling rejection before voice, structured model
errors, English skip, readiness/release and LOW_RAM publication-before-release.
Updated two obsolete Task 5B assertions for approval wording and the implemented
localizer; all its existing regression coverage passes. Real Hindi TTS follows in M4.

## M4 — real Hindi preview complete; hi_technical_ready=true

One TestClient run, job `j_b7dc8b4c95d7`, canonical Water Cycle `c1f63f0ed69b`,
`hi-female-1`, beginner/science/60 s. Hindi was approved only in the test Settings;
no `.env` or production approval was changed. Real IndicTrans2 initialized (2.529 s);
the real localizer reused its M2 validated translation cache, avoiding duplicate
translation inference. A guarded planner transport allowed **zero Ollama calls**;
the canonical English plan remained byte-identical.

Stages: plan cached **4 ms**, validate **1 ms**, translate cached **596 ms**
(includes local model-identity hash check), real Kokoro **14,357 ms** (11 beats,
one already cached, 68.409 s speech), real timeline **1,591 ms**; export explicitly
skipped **0 ms**. Job total 16.552 s; wall including model init 19.216 s.
Preview was ready before the skip-export operation. `mock=false`, `fallback=false`.

WAV: **24 kHz, 73.1 s**, RMS **0.09674**, peak **0.76935**; timeline **2193 frames**,
30 fps, tempo **1.0**, **14 caption cues**. UTF-8 SRT equals timeline-derived SRT.
HTTP 200 nonempty WAV (3,508,844 B), M4A (640,045 B), SRT (2,532 B), timeline
(4,460 B), props (9,545 B), lesson JSON; validated RenderProps/identity. MP4 URL
null, no lesson.mp4 generated, export_status skipped. Complete localization,
English narration fallback **0/11**; five distinct localized-note length warnings,
no tempo/over-90-second warning. Narration expansion 1.205x chars / 1.504x words.
Technical terms preserved. This proves technical preview, not pronunciation or
perceptual synchronization approval. Full report: `scratch/task6/hi_smoke.json`.

## M4b — Hindi review pack complete; human approval pending

`scratch/review/hi/` contains 20 English/Hindi pairs and technical examples in
`text_pairs.json`, warnings/statistics, the actual `narration.wav`, matching
`lesson.srt`, and `CHECKLIST.md`. No reviewer decision is invented. Next user
action: listen/read this pack and record approval/corrections. Only then explicitly
set `APPROVED_LANGUAGES=en,hi` and restart; Kannada production remains disabled.

## M5 — documentation and final regression complete

Updated API, language, frontend integration, measured test log and this checkpoint.
Final focused suite: **78 passed, 13 subtests passed in 2.12 s**.
Full backend: **197 passed, 1 skipped, 42 subtests passed in 41.99 s**.
Only skip is `test_task3.py:118` (real renderer exists); no pytest warnings.
Command: specified Kavach Python, CPU/offline env, bytecode disabled,
`-m pytest backend/tests -q -rs -p no:cacheprovider`.

Final edge-case coverage found and fixed overlapping numeric-unit matches:
`9.8 m` plus `m/s²` now protects the full `9.8 m/s²`. Formula highlight fragments,
plain SI units, code-only narration eligibility, placeholder loss during a beam-5
retry, all six real fixtures and current-source export provenance are tested.
The production export verifier checks localization provenance; its memo rechecks
when canonical plan/localization records change. Exporter internals are unchanged.

Cache-only CLI checks for both `--lang hi` and `--lang kn` passed under a guard
that would fail on translation inference. Cached Hindi provenance remains valid
after actual timeline publication, and no model was initialized for these checks.
`APPROVED_LANGUAGES` still resolves to **en**. Review pack has exactly 20 pairs.
`git diff --check` passed; routine Git LF/CRLF notices only. Frontend file hashes
match the recovery/pre-continuation values. No model/package installation, network
AI, planner generation, real MP4 rendering, commit/tag/push or Task 7/VQ1 work.

Continuation-owned files (preexisting user modifications in overlapping files kept):
- Modified: `backend/app/config.py`, `localize/__init__.py`, `main.py`,
  `orchestrator.py`, `pipeline_ops.py`, `backend/tests/test_task5b.py`.
- Added: `backend/app/language_policy.py`, `localize/model.py`, `localize/terms.py`,
  `localize/translate.py`, `backend/localize_lesson.py`,
  `backend/tests/test_task6_localize.py`, `test_task6_pipeline.py`.
- Updated docs: `api-contracts.md`, `narration-languages.md`,
  `frontend-integration.md`, `test-log.md`, this `task6-status.md`.
- Added six validated lessons plus six diagnostic sidecars in
  `data/samples/localized/`. Retained ignored reports in `scratch/task6/`,
  review artifacts in `scratch/review/hi/`, and real Hindi audio/timeline in cache.
- M0b's `test_task6_identity.py` was reused unchanged.

**Status:** M1/M2/M3/M4/M4b/M5 technically complete. `hi_technical_ready=true`,
`human_approved=false`. Remaining decisions: human Hindi meaning/pronunciation/
caption review; Kannada voice remains Task 7. Kannada has the explicitly recorded
partial translation fields, not silent success. Hindi MP4 and browser visual
acceptance were deliberately outside Task 6 verification.

**Exact next step:** review `scratch/review/hi/CHECKLIST.md`, text pairs and WAV/SRT,
record corrections/approval, and only upon explicit human approval set
`APPROVED_LANGUAGES=en,hi` and restart. No automatic approval or further feature
work is authorized by this checkpoint.

## M0 — preflight complete

- Target: `C:\Users\ROG\VisualTeacher-varun`, branch `main`, HEAD
  `03bece6ae9308a98340af78f801d8d734de8b7b3`.
- Initial Git status matches recovery: eleven unstaged tracked files, no staged
  files or nonignored untracked files. Existing changes: `backend/app/lessons_api.py`,
  `main.py`, `pipeline_ops.py`; `backend/tests/test_foundation.py`, `test_task5b.py`;
  `docs/api-contracts.md`, `frontend-integration.md`, `task5-status.md`, `test-log.md`;
  `web/src/app/App.tsx`, `CreateForm.tsx`. Preserve all of them.
- Baseline: specified Kavach Python, `DEVICE=cpu`, `PYTHONUTF8=1`,
  `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, bytecode disabled;
  `python -m pytest backend/tests -q -rs -p no:cacheprovider`:
  **144 passed, 1 skipped, 42 subtests passed in 41.44 s**. Skip:
  `test_task3.py:118` because the real renderer exists. No warnings reported.
- Mocked regression ran before real model initialization. Tests use only
  synthetic temporary media fixtures; no Kokoro/IndicTrans inference or Remotion.
- IndicTrans2 files exist at `C:\Users\ROG\Kavach\models\indictrans2`:
  config, tokenizer config/Python, SRC/TGT SentencePiece files and dictionaries,
  local modeling/configuration Python, safetensors and PyTorch weights.
- One offline CPU initialization succeeded: `IndicProcessor(inference=True)`,
  `AutoTokenizer` and `AutoModelForSeq2SeqLM` with `local_files_only=True`,
  `trust_remote_code=True` for the existing local implementation, float32,
  `.eval()` and configured CPU device. Classes: `IndicProcessor`,
  `IndicTransTokenizer`, `IndicTransForConditionalGeneration`. Transformers
  **4.46.1** unchanged. Measured model/tokenizer/processor load: **0.457 s**
  (excludes imports). No `.generate()` call, downloads or package changes.
- Read-only font check: Noto Sans Devanagari and Noto Sans Kannada WOFF2 files
  exist at weights 400/500/600 with licences. `web/src/lesson/fonts.ts` maps hi/kn
  correctly and loads these exact local filenames using `loadFont` + `staticFile`.
  No frontend edits or browser/font rendering claims.
- Contracts/interfaces inspected: `PlanRequest`, `lesson_key`, planner cache,
  production plan op, `Orchestrator`, `PipelineRun`, `NarrationContext`,
  `run_voice`, variants, API availability/health and localization stub.
- No genuine model/dependency/font blocker. Sandbox cannot execute the venv's
  base Python; approved outside-sandbox execution works.

## M0b — canonical English identity complete

Existing `lesson_key` already excludes language, voice and speed. English
Water Cycle / beginner / 60 s / effective science / CPU model / p12-task4 /
schema 1.0 remains `c1f63f0ed69b`. No hash algorithm, model/prompt/schema input,
plan cache layout or downstream identity check should change.

The missing guarantee was explicit canonicalization at both orchestration
boundaries: key prediction and production plan retrieval constructed
`PlanRequest(language=request.language)`. Both now construct `language="en"`
before their calls, preserving the original request language on `PipelineRun`.
Localized lessons keep the canonical ID; variants remain `<lang>-<voice>-<speed>`.
No IDs are overwritten after planning. Planner internals keep their CLI/request
metadata contract unchanged.

New tests are added before implementation to cover legacy IDs, English requests
at both boundaries, real cache validation/immutability/no HTTP calls, a first
mocked generation followed by hi/kn cache reuse, planning-input isolation,
18 distinct variants and localized Hindi voice identity using a fake engine.

Before changing existing identity logic, the focused suite produced **4 failed,
12 passed in 0.40 s**. The four intended failures capture Hindi/Kannada reaching
`lesson_key` and `plan_lesson` with `language=hi/kn` rather than canonical `en`.
English compatibility, actual cache reuse, key isolation and fake-voice identity
already passed. The implementation changes only the two `PlanRequest`
construction sites in `orchestrator.py` and `pipeline_ops.py`.

After the two-line fix: **16 passed in 0.33 s**. Tests prove:
- en/hi/kn predict the same legacy canonical ID and pass English `PlanRequest`s
  to both the key function and real cached planner.
- Existing English `plan.json` validates, retains its bytes and mtime, and
  requires zero Ollama HTTP calls for all three language requests.
- One initial mocked Ollama generation is followed by hi/kn requests with no
  further inference or HTTP calls; their `PipelineRun` IDs equal the plan ID.
- Topic, level, duration, effective subject, model and prompt changes isolate keys;
  the existing schema-version hash component remains covered without a version bump.
- 18 language/voice/speed variants have distinct folders under one plan ID.
- A localized Hindi lesson passes the real `run_voice` identity/variant checks
  with a fake engine and temporary synthetic samples. This is an identity test,
  not a real translation, voice-quality or Hindi-preview acceptance claim.

Final full backend regression: **160 passed, 1 skipped, 42 subtests passed in
41.66 s**, using the same CPU/offline environment and command as M0. The only
skip remains `test_task3.py:118`; no pytest warnings. `git diff --check` passed
(Git reports routine LF-to-CRLF notices for existing working-tree files).

Task-owned changes: two one-line backend boundary fixes, new
`backend/tests/test_task6_identity.py` and this checkpoint. Existing Task 5C
changes in `pipeline_ops.py` were preserved byte-for-byte outside the changed
request line. Existing user changes and `web/` remain untouched. No commit,
tag, push, pull, merge, rebase, reset or stash was performed.

Production hi/kn availability stays disabled during this identity milestone.
The placeholder localizer and health readiness are unchanged. No MP4 render,
real TTS generation, planner inference, Task 7 or VQ1 work.

## Human review approval — 27 October 2026

- Reviewer: Project owner.
- Review date: 27 October 2026.
- Hindi translation: Accepted.
- Hindi narration and pronunciation: Accepted.
- Overall Hindi quality: Approved for hackathon use.
- Production configuration: `APPROVED_LANGUAGES=en,hi`.
- Kannada: Not approved; Task 7 pending.
- Hindi video rendering: Still requires final frontend/MP4 verification.

The project owner personally reviewed the Hindi translation pairs and narration
WAV in `scratch/review/hi/` and explicitly approved them for hackathon use.
This entry supersedes the earlier pending-human-approval status. All preceding
milestone documentation and test results remain historical records unchanged.
