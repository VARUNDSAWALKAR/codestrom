# VQ1 backend checkpoint — 28 October 2026

Status: isolated backend framework implemented; **M7 semantic-quality acceptance
FAILED**. VQ1 is not claimed complete. Renderer contract remains proposed and no
production integration is enabled. Final regression/audit recorded below.

## M0 — baseline and discovery

- Repository `C:\Users\ROG\VisualTeacher-varun`, branch main, HEAD
  `03bece6ae9308a98340af78f801d8d734de8b7b3`. Existing Task 5/6/7 changes,
  localized samples and Varun's two frontend edits preserved. Baseline inventory
  and SHA256s: `scratch/vq1/baseline.json` (copied from staging at final audit).
- Specified interpreter, CPU/offline flags: **220 passed, 1 skipped,
  42 subtests in 46.57 s**. Only skip: test_task3.py:118, renderer exists.
- Read AGENTS, CLAUDE, complete task-split, architecture, scene-components,
  lesson-schema, prompts, pipeline, test-cases, test-log, licenses, data schema
  and topic set. `docs/animation-plan.md` is absent. Historic "Task 5 not
  implemented" and GPU-only Parler statements are stale; current Task 5/6/7
  code/status and pipeline override establish actual behavior.
- Inspected planner schema/validation/prompt/client, cache, localization,
  narration enumeration, timeline schema/build, orchestration and read-only
  frontend types/timing/Diagram/geometry. Actual prompt is p12-task4 (not p1).
- Stable scene IDs sN; steps have **no separate IDs**, only stable indexes.
  Beat IDs are sN.intro and sN.stepK (zero-based). Localization preserves
  scene order/type, step order/count, code, expressions and narration presence.
  Existing hi/kn Water Cycle timelines match the canonical beat inventory.
- Proposed independent `cache/visuals/` namespace; canonical English content
  fingerprint, separate visual versions/model digest/options. No language,
  voice, speed or audio timing in semantic identity. A binding adapter verifies
  localized structure and maps beat fractions to each measured timeline.
- Existing render props cannot carry VQ1. No production wiring/schema change.
  Frontend remains responsible for pixels, fonts, collisions and frame evaluation.
- Cached sources include Water Cycle, Binary Search, Python loop, Photosynthesis,
  Concave Lens. Binary Search example values/line highlights are inconsistent;
  Concave Lens incorrectly describes myopia as blurred near vision. Preserve
  sources; fixtures identify their limitations, never certify these claims.
- Next: implement bounded VisualSpec, validation, then isolated planner/cache.

## Rules versus design choices

Offline/no code execution/audio-derived timing/CPU support are project rules.
Safe region, vocabulary, complexity limits and interpolation semantics below
are proposed VQ1 choices until Varun confirms. No asset file/license is assumed.

## M1 — separate VisualSpec

Created `backend/app/visuals/schema.py`: finite normalized geometry in the
64,120–1216,580 content region; typed primitives, seven layout families and
exactly six action kinds. Strict discriminated unions, bounded declarative paths,
source text bindings and explicit legacy decisions. No production model changed.
Empty approved asset set; three names are provisional only. Tests pending M6.

## M2 — source-aware validation

`validate.py` checks canonical fingerprint/order, scene-local beats, references,
IDs, containment/depth, geometry bounds, assets, text safety and state conflicts.
Invalid data returns structured diagnostics without specialized publication.
No semantic accuracy certification. `geometry.py` contains only a bounded
analytic linear-plot helper; no optical or chemistry solver is claimed.
`bind.py` verifies localized structure and maps fractions onto real timeline
frames. Literal supplemental English labels are warned about in non-English.

## M3 — optional semantic intent planner

`planner.py`: separately versioned visual-p1, pinned installed Qwen 4B, injectable
inference, constrained Intent JSON. Model selects roles, shapes, coarse slots,
links, beat actions; deterministic compiler constructs bounded primitives.
No topic-title branches. Optical/quantitative simulation intent requires solver
and falls back. At most one targeted repair per selected scene, no transport
retry/model switch, CPU num_gpu=0, temperature=0/seed=7, context6144/output1800.
Local tags digest establishes model identity; no cloud/proxy/redirect endpoints.
No API/job wiring. Thin CLI `python -m backend.visualize_lesson --lesson ID --scene s2`.

## M4 — independent visual cache

`cache.py`: `cache/visuals/<sha256>.json`, one checksummed spec envelope,
fsync and atomic replacement. Key includes canonical full-content fingerprint,
all five visual versions, model tag+digest, generation options and scene selection.
Hits revalidate schema, source and provenance. Corruption fails closed with
diagnostic and no inference/overwrite; old versions/media remain in place.
Process lock serializes planning/publication. Cache hits require zero chat calls;
local digest discovery may query tags. Cross-process duplicate inference is not
prevented (CLI is an explicit developer operation, production has one worker).
Tests and fixtures are next; no real inference has run yet.

## M5 — development fixtures and renderer feasibility

Fourteen validated JSON fixtures plus inventory and a synthetic Ohm's-law input
under `backend/tests/fixtures/visuals/`. Eight required topics covered; an
additional authored sorted-array example avoids silently fixing the cached
Binary Search source. Five held-out vocabulary checks: speed/velocity, heart,
methane, circle area and states of matter. These authored fixtures establish
representation/validation feasibility, **not LLM generalization evidence**.
Concave Lens has explicit solver/source-quality fallback. Existing Newton sample
keeps formula legacy, with a qualitative force/cart scene. Mathematical Function
uses the tested y=x+1 construction; no arbitrary expression evaluator.
Ordinary SVG shapes/paths/groups plus Remotion frame interpolation suffice for
these examples; actual frontend performance, text fitting and visual QA remain
Varun's work. No renderer implementation/approval is claimed.

## M6 — mocked contract tests

Initial focused result: **89 passed in 0.45 s**, no model calls. Coverage includes
all seven layouts, supported primitives/six actions (asset rejection because
manifest is empty), reference/geometry/timing/state/group/security/complexity
failures, deterministic composition, timeout/one repair/explicit fallback,
cache hits/invalidation/corruption/atomic interruption, canonical en/hi/kn IDs,
localized labels/clocks, old-media preservation and inert source code.
New files only; the production API/planner/TTS/timeline/exporter are untouched.
Next: full compatibility regression, then limited genuine Ollama evaluation.

## M7 — limited genuine CPU evaluation; quality gate not met

All mock tests passed before inference. Pre-inference full compatibility suite:
**309 passed, 1 skipped, 42 subtests in 47.47 s**. The installed model digest is
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
Local /api/ps confirmed size_vram=0, context6144. No model switch/download.
One scene per source, never new production lesson planning, translation, TTS,
timeline generation or media export.

| Source / prompt | Genuine wall seconds | Calls / repairs | Result |
|---|---:|---:|---|
| cached Concave Lens s2 / visual-p1 | 32.763 | 1 / 0 | unsupported fallback, no objects |
| cached Water Cycle s2 / visual-p1 | 34.901 | 1 / 0 | unnecessarily requires solver; fallback |
| cached Binary Search s3 / visual-p1 | 31.168 | 1 / 0 | unnecessary solver request; fallback |
| synthetic held-out Ohm's Law s2 / visual-p1 | 22.860 | 1 / 0 | unsupported fallback |
| same Water Cycle / visual-p2 | 73.020 | 2 / 1 | schematic intent; repeated anchors after repair, initially rejected |
| same held-out Ohm's Law / visual-p2 | 20.217 | 1 / 0 | spatial,4 objects/3 reveal actions,75% beat coverage; weak label diagram |

Seven genuine chat calls total, one repair, about215 seconds aggregate wall.
Initial fallback rate4/4. Revised prompt original fallback rate1/2. Every
published decision remained structurally valid and source-matched; every repeat
request hit validated cache with zero chat calls (about1.5–2 ms for p2).
Original reports/raw responses preserved in `scratch/vq1/acceptance.json`,
`scratch/vq1/*.raw.json`, and `scratch/vq1/p2/`.

visual-p2 narrows action fields into static/travel branches, clarifies qualitative
science is supported and adds one unrelated settling-particle example. No
production prompt changed. Final geometry-actions-v2 deterministically resolves
duplicate preferred anchors into nearest free slots, without changing references
or relaxing geometry/action validation. The **saved** genuine p2 responses were
recompiled/revalidated and cache-tested with **zero new Ollama calls**:
`scratch/vq1/replay.json`. Water Cycle now has9 objects/5 reveals, full beat
coverage; Ohm's Law has4 objects/3 reveals,75% coverage. A structural pass is
not a semantic pass. Both emit limited_visual_mechanism diagnostics.

Manual inspection of JSON (not rendered-pixel QA): Water Cycle remains process
rectangles instead of sun/reservoir/cloud/rain. Ohm's Law remains circuit/
voltage/current labels with one arrow, without resistor/source circuit topology.
Meaningful concrete-mechanism coverage is inadequate in both; **0/2 revised
cases accepted for semantic quality**. No scientific accuracy approval is claimed.
Known source inaccuracies in Binary Search/Concave Lens were not corrected.
Held-out authored fixtures validate but do not establish model generalization.

The second pass does not demonstrate sufficient quality gain for its CPU cost.
Consider a smaller compositional intent vocabulary/verified construction set,
with model roles and deterministic geometry, rather than more generic shape
prompting. Existing compiler is topic-independent; no per-title animation
templates were introduced. Stop expensive evaluation here, preserve diagnostics,
and keep production disabled. This is the remaining VQ1 completion blocker.

## M8 — renderer handoff

`docs/vq1-renderer-handoff.md` documents all fields, primitives, seven families,
six actions, style/coordinate conventions, fractions/start/end/held states,
group/relationship semantics, localized source bindings, assets/fallbacks/limits,
fixtures and objective browser/MP4 tests. Arc-length sampling, anchors/collisions,
asset approval and future production props/cache changes require joint review.
Contract is **proposed until Varun confirms**; no frontend is implemented here.
MP4 renderer-build/spec/font/asset fingerprints are future integration work;
existing exporter/media are unchanged.

## M9 — final hardening and regression

Final mocked tests additionally cover malformed envelopes, all style/version
tokens, duplicate-slot deterministic composition and particle/action complexity.
Source Lesson is revalidated at the boundary, including code display line refs.
One intermediate test failed because its inert-code fixture shortened the code
while retaining old line refs; corrected fixture preserves the source line count.
No existing tests were weakened. Final focused result: **111 passed in0.55 s**.
Final full suite: **331 passed, 1 skipped, 42 subtests in46.21 s**.
Only skip remains test_task3.py:118 (renderer exists); no pytest warnings.
`git diff --check` passed; Git emitted only pre-existing LF-to-CRLF notices.

Final SHA256 audit: **197 pre-existing files unchanged**, including every existing
tracked/untracked source/doc/frontend file and .env. **210 existing production
lesson/audio/translation cache files unchanged**; no MP4 removed or regenerated.
All29 scoped new files match their publication manifest. Effective approvals
still en,hi; Kannada disabled. No commit/push/tag or Git history operation.
`scratch/vq1/final-verification.json` records the audit and read-only mapping of
the authored Water Cycle spec onto actual cached en/hi/kn timelines: four actions
in each, different language-specific frame boundaries, source IDs unchanged.
No caption/audio/timeline generation, translation model or TTS loading occurred.

New implementation files only:7 package Python modules,2 package JSON manifests/
schema, backend/visualize_lesson.py, backend/tests/test_vq1.py,14 spec fixtures,
one held-out source, fixture inventory and the2 VQ1 documents. No package/model/
font/illustration added; existing licence documentation remains sufficient.

Next: owners review the proposed contract and failed semantic examples; choose
the smallest general construction vocabulary that improves these mechanisms.
Varun may prototype the meaningful authored fixtures while that decision is made.
Do not activate generated specs in production or claim VQ1 done before semantic
acceptance and renderer feasibility/visual QA pass. No further roadmap task begun.

## Milestone disposition

| Milestone | Result |
|---|---|
| M0 | Baseline/audit complete |
| M1 | Proposed separate VisualSpec implemented |
| M2 | Strict/source-aware validation and safe fallback implemented |
| M3 | Optional local planner/compiler implemented; semantic quality inadequate |
| M4 | Independent cache/integrity/reuse implemented and tested |
| M5 |14 authored validated fixtures and feasibility assessment complete; frontend confirmation pending |
| M6 |111 mocked tests passing |
| M7 | Limited real evaluation executed; semantic acceptance FAILED |
| M8 | Complete proposed handoff delivered; Varun confirmation pending |
| M9 |331 passed/1 skipped/42 subtests; pre-existing files/media preserved |

## VQ1.1 — audit and root causes (28 October 2026)

Build on the existing sidecar; no production integration. main/03bece6 and all
pre-existing changes preserved. Snapshot: scratch/vq11/baseline.json.
Read current rules, architecture/scene/planner contracts, all VQ1 modules,
handoff, tests, authored fixtures and saved real raw outputs. Frontend Lesson
still dispatches legacy scene types; Diagram uses box/arrow geometry. No
VisualSpec renderer exists yet. Existing visual-v1 schema is sufficient.

Failure classification from actual records:

| Saved case | Root causes (categories from VQ1.1 request) |
|---|---|
| p1 Concave Lens | Unsupported ray geometry correctly falls back; semantic correctness unavailable (10); prompt's broad unsupported choice obscures useful conservative alternatives (9) |
| p1 Water Cycle | Mechanism named but falsely requires a solver (1,9); invalid title target (6), duplicate preferred anchors (5); entity shapes lack transfer semantics (7) |
| p1 Binary Search | Wrong flow layout (2), invented/copying inconsistent 8 not in source array (10), repeated placements (5), destination on static actions (9); false solver choice (1) |
| p1 held-out Ohm | Abstract circuit/voltage/current shapes instead of topology (3,7), repeated anchors (5), unnecessary unsupported fallback (9) |
| p2 Water Cycle | Identifies cycle but substitutes process rectangles (3), chooses flow instead of spatial mechanism (2), repeated anchors (5), reveal-only composer lacks physical entities/transfers (7) |
| p2 held-out Ohm | Valid causal labels but no recognizable source/resistor geometry (3,7,10) |

No observed excessive geometry (4). VisualSpec limits were not the limiting
factor (8); authored meaningful fixtures already fit. Validation failures and
semantic-quality failure remain separate. No prompt tuning before this audit.

### VQ1.1 implementation checkpoint

Added `semantic.py`: typed family union (array_grid,spatial,graph_network,
unsupported), source quotes, entities/relations and ordered beat changes. No
model shapes/slots/style/geometry/timing. Added `compose.py`: reusable entity
motifs, material-transfer routes, arrays/bounds/selection/comparisons/swaps and
graph topology/edge-following visits, all emitted as existing VisualSpec.
Coordinate generation is deferred: linear_points remains available for authored
fixtures, but automatic domain/scale grounding needs a separate reviewed contract.

Existing runner, localhost client, atomic cache, validator and binder reused.
`plan_semantic_visuals` opts into VQ1.1; existing plan_visuals default and tests
remain compatible. CLI defaults to VQ1.1 with explicit --legacy-intent escape.
Versions visual-semantic-p1 / semantic-intent-v1 / semantic-composer-v1 isolate
cache keys. Validator accepts the two known producer version pairs; visual-v1
JSON Schema is unchanged. Old fixtures, cache artifacts and raw evaluations
will not be rewritten. Tests/fixtures next, before genuine inference.

### VQ1.1 deterministic verification checkpoint

Baseline rerun: **331 passed,1 skipped,42 subtests in46.08 s**. New mocked and
legacy VQ1 tests: **163 passed in0.69 s** (52 new tests). Eight separate fixtures
under backend/tests/fixtures/visuals_v11/; none of the14 old fixtures changed.
Source-grounded Water Cycle spatial transfers, corrected authored array bounds,
graph traversal and two held-out authored sources (settling and pairwise swap)
compose successfully. Cached inconsistent Binary Search and accurate-ray lens
request fall back. Ohm source/resistor symbols depict a connection, but this
authored fixture is partial: no complete closed circuit or quantitative law.
No authored/mock result is counted as real-model success. Coordinate generation
remains explicitly deferred. Next:3 real cached-source CPU evaluations, max1
repair each; no further prompt tuning loop if semantic quality remains weak.

### VQ1.1 genuine evaluation — semantic recovery FAIL

Model qwen3:4b-instruct-2507-q4_K_M, installed digest
0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0.
CPU num_gpu=0; /api/ps confirmed size_vram=0 and context6144. Same temperature0,
seed7, output limit1800. No downloads, model switch, new lesson plans or external
API. Three cached English sources; at most one repair per case. No additional
prompt revision or genuine inference after these failures.

| Real source / scene | Wall seconds | Calls / repairs | Intent family | Final result |
|---|---:|---:|---|---|
| Water Cycle c1f63f0ed69b / s2 |80.859|2 /1|spatial|Invalid source grounding; safe fallback |
| Binary Search d09d4030959b / s3 |26.262|2 /1|array_grid|Inconsistent source/middle8; safe fallback |
| Held-out Photosynthesis c333b21b73c7 / s3 |80.861|2 /1|spatial|Entity type/reference errors; safe fallback |

**6 actual chat calls,3 repairs,187.982 s aggregate wall.** All6 returned intents
passed structural Pydantic parsing, but **0/6 passed source/semantic consistency**.
All3 final VisualSpecs passed validation as explicit legacy fallbacks, with0
specialized objects/actions and0 explanatory beat coverage. Warm cache verified
for all3 with **zero fresh inference** (actual timings in acceptance.json).
Final fallback rate3/3; legitimate source-protection fallback for Binary Search
is distinguished from unexpected failures on the two clean-source evaluations.
**0/2 clean representative/held-out cases accepted for explanatory quality.**

Family/entity extraction improved versus visual-p2's process boxes, but this is
not sufficient recovery: no acceptable generated VisualSpec was produced. The
water response paraphrases earth surface instead of quoting Earth's surface,
calls it a body, and uses sun-to-water material transfer without a declared flow.
Its condensation transfer is not supported by directional movement evidence.
The Binary Search response copies middle8 absent from [1,3,5,7,9] and incorrectly
asserts5>7. The source itself is inconsistent; it was not edited or silently
corrected. The held-out biological response calls roots/stomata reservoirs and
references undeclared chloroplasts,air,light; it conflates light capture with
heating/material transfer. Rejecting these is intentional, not a reason to
weaken source/geometry/reference validation.

Preserved raw model messages/responses: scratch/vq11/{water_cycle,binary_search,
heldout_photosynthesis}.raw.json. Original run statistics: acceptance.json.
Manual source/JSON assessment: evaluation.json. These assessments are not rendered
visual QA or human scientific approval. The photo source was held out from
VQ1.1 authored fixture/prompt development; it was an older cached canonical plan,
not freshly planned for this test. Authored tests remain a separate category:
5 qualitative positive examples,2 safe fallbacks,1 partial connection example.

### VQ1.1 final regression, compatibility and disposition

Final full backend suite: **386 passed,1 skipped,42 subtests in46.06 s**.
All55 new VQ1.1 tests passed within that run; all111 legacy VQ1 tests remained
unchanged. Earlier targeted run was163 passed (52 new plus111 old). The final
three additional checks cover signed quantities, safe internal namespacing and
non-radiating force application. One intermediate new ID-boundary fixture was
33 characters rather than the allowed32; corrected its test input. No existing
tests weakened/removed/skipped. No pytest warnings. git diff --check passed;
only existing Git LF-to-CRLF notices. Search confirmed no sidecar import/wiring
in main,pipeline_ops,orchestrator (rg correctly returns1 for no matches).

18 scoped files:5 existing files modified (visuals/planner.py,visuals/validate.py,
backend/visualize_lesson.py and the2 VQ1 documents),13 new (semantic.py,compose.py,
semantic.schema.json,test_vq11.py and8 fixtures+inventory). Original documents
retained with append-only VQ1.1 sections. Original visual.schema.json and all14
VQ1 fixtures unchanged. No frontend or production source/config contracts changed.

SHA256 audit: **221 other pre-existing files unchanged** and **218 pre-existing
cache files unchanged**, including lesson/audio/translation artifacts and all
older visual caches. No valuable artifacts removed. The new authored spatial
fixture binds6 actions to actual cached en/hi/kn timelines with the same canonical
identity and language-specific frames. Hindi/Kannada supplemental English labels
emit3 explicit review warnings each; no translation/TTS/timing regeneration.
.env and effective approval remain en,hi; Kannada remains unapproved.
Full audit: scratch/vq11/final-verification.json. No commit/push/tag/reset/stash,
package/model/font/asset installation, real speech generation or MP4 rendering.

**Disposition: implementation and verification finished; VQ1.1 semantic-success
Definition of Done is NOT met.** Useful deterministic components and evidence
are retained; sidecar remains outside production. Stop further prompt-tuning
loops. A next backend decision could replace free quotation/entity IDs with
source-assigned candidate references and decide how to treat inconsistent
canonical examples; that is proposed follow-up, not implemented/claimed here.
Varun can implement the unchanged VisualSpec primitive/state interpreter against
the authored spatial/array/graph fixtures, review collisions and Indic labels,
and verify browser/MP4 parity before any separately approved production wiring.
