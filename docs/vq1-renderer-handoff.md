# VQ1 renderer handoff — proposed contract, 28 October 2026

**Backend implemented; frontend proposed until Varun confirms feasibility.**
Nothing in this document changes Lesson v1, Timeline v1, current RenderProps,
the production API or production jobs. Do not add this to the production renderer
until the two owners agree on the integration contract and acceptance criteria.

## Entry points and files

- Models: `backend/app/visuals/schema.py`.
- Exported schema: `backend/app/visuals/visual.schema.json` (test checks equality
  with `VisualSpec.model_json_schema()`).
- Validation: `validate_visuals(candidate, canonical_english_lesson)` returns
  `ValidationResult(spec | None, fallback, diagnostics)`.
- Optional planning: `plan_visuals(canonical, settings, inference=None,
  model_identity=None, options=None, scene_ids=None)`; keyword arguments only
  after settings. Returns spec, diagnostics, statistics, cache key.
- Development CLI: `python -m backend.visualize_lesson --lesson <path|id>
  --scene s2`. Without --scene it plans all explaining scenes. It never creates
  a lesson, speech, timeline or MP4. Exit2 means all scenes fell back.
- Fixtures: `backend/tests/fixtures/visuals/*.json`; each fixture contains
  `source`, `spec`, origin, review notes and expected behavior. They are not
  production render props. `inventory.json` lists them.
- Closed assets: `backend/app/visuals/asset-manifest.json`; approved set EMPTY.

## Identity and source mapping

VisualSpec has visual_schema_version=visual-v1, canonical lesson_id,
source_fingerprint (SHA256 of canonical Lesson's complete normalized model dump),
provenance and ordered scenes. Provenance records visual-p1, model tag/digest,
primitives-v1, assets-v1-empty, geometry-actions-v2 and a configuration fingerprint.
VisualSpec is English-source semantic data, not a localized lesson copy.

Every source scene has exactly one SceneVisual in source order. SceneVisual has
scene_id, optional layout, mechanism, accuracy, limitations, objects,
relationships, actions and optional fallback. IDs are scene-local. References
must be resolved in that scene, never by a global object ID alone.

Steps have no independent IDs. Step references use zero-based indexes, matching
existing sN.stepK narration IDs. Intro is sN.intro only if narration is nonempty.
Do not synthesize intro beats where the source has none. `bind_timeline` verifies
localized protected structure and existing RenderProps beat mapping, then binds
actions to the language's actual measured beats. Geometry is reused across
en/hi/kn; frame numbers/durations are not reused across languages.

## Canvas and placement

Render at 1280x720. Safe content rectangle is x64..1216, y120..580:
`pixelX=64+1152*x`, `pixelY=120+460*y`. Geometry coordinates lie within [0,1].
Header, captions and progress remain outside this rectangle. These coordinates
are **proposed VQ1 nominal anchors**, not permission to draw through captions.

Position means center for all positioned objects. Width is a fraction of1152;
height is a fraction of460. Circle/marker/particle radius is a fraction of460,
so pixel radius=`460*radius` on both axes. Ellipse rx/ry are separate fractions
of width/height. Polygon/path points are absolute content coordinates.
There are no group-local coordinates, rotations, arbitrary transforms or paths.

Renderer handles pixel placement, script-aware text sizing, collision detection
and final fitting. Preserve semantic ordering/containment/connector endpoints.
Do not independently move optical rays, numeric graph points or force vectors
to fit labels. Unsupported accuracy-sensitive geometry should fall back. Existing
fixtures do not assert ray tracing or numeric physical trajectories.

Intent compiler uses nine anchors, x=.18/.5/.82 and y=.18/.5/.82. Duplicate preferred
anchors are assigned to the nearest free anchor by squared pixel distance with
stable slot-order ties; placement_adjusted diagnostics record this. This deliberately
small subset is not the complete VisualSpec geometry vocabulary. Human-authored
fixtures can use richer validated geometry. Renderer may need a second layout
pass; confirm anchor behavior jointly before production integration.

## Object vocabulary and allowed properties

All objects: id (lowercase slug,1..32 chars), role (plain semantic text,1..160),
style token (default primary), optional label. No inline markup/CSS/URLs/paths.
Unknown fields are errors. Objects render in array order, last on top.

| kind | Additional fields | SVG/React implementation |
|---|---|---|
| rectangle | position,width,height | rect centered on position |
| circle | position,radius (0..0.5,exclusive zero) | circle, isotropic pixel radius |
| ellipse | position,rx,ry (0..0.5,exclusive zero) | ellipse |
| polygon | points (3..12) | polygon; no model SVG string |
| line / arrow | start,end | line; arrowhead built by renderer |
| path | start,segments (1..8) | construct d internally from typed coordinates |
| text | position,width=.25,height=.12,label required | escaped React text, local font |
| group | children (1..16 object IDs) | organizational group, no transform |
| marker | position,radius<=.02 (default .008) | small circle |
| highlight_region | position,width,height | transparent semantic emphasis rect |
| particles | positions (1..32),radius<=.02 (default .005) | fixed repeated circles |
| asset | asset_id,position,width,height | closed manifest only; currently rejected |

Path segment is either `{kind:line,end:{x,y}}` or
`{kind:cubic,control1:{x,y},control2:{x,y},end:{x,y}}`. Each segment starts at
the previous segment's end (first starts at path.start). No SVG text is accepted.
Control hull and complete object extents must fit the content region. Zero-length
lines, zero-area/self-intersecting polygons and repeated vertices are rejected. This is geometry validation, not a
physics or chemistry engine. Mathematical Function fixture's five points come
from tested `linear_points(1,1,0,4,0,6)`; arbitrary formulas are never evaluated.

Group children are already present as flat objects: **do not render them twice**.
Grouping is an organizational/constraint graph, not a separate z-order override.
Containment/belongs_to edges participate in cycle/depth/single-parent checks.
No action can target a group: animate its children explicitly.

## Labels, localization and fonts

Two discriminated label forms:

```json
{"kind":"source","field":"text","step_index":0}
{"kind":"literal","text":"7"}
```

Scene source fields: heading,center,expression,code (step_index=null).
Step source fields: text,note,output (valid step_index required). Resolve against
the **current localized lesson** after identity validation, using `resolve_labels`.
Source bindings reuse Task6 translation; code, expression, output remain exact.
Literal supplemental labels are retained English and produce explicit warnings
for non-English. No new translation integration exists in VQ1. Review/replace
supplemental labels before shipping Indic scenes. `role`/`mechanism` are metadata,
not automatically visible captions or narration. Do not substitute them for
localized labels without an explicit reviewed decision.

Every rendered text gets the lesson lang and existing local script font family.
Hindi/Kannada require taller line height, script measurement, wrapping/shrinking
and no clipping. Never insert labels/code as HTML/SVG markup. Source code is
inert display text; no eval/execution, imports, or simulated execution outputs.
Continue to use the existing audio/caption track; VQ1 does not create narration.

## Seven layout families

| layout | Meaning / renderer responsibility |
|---|---|
| flow_cycle | causality/sequence/return links; shapes may be entities, not sentence boxes |
| spatial | qualitative locations, directions, containment and scene relationships |
| array_grid | ordered cells, indices, bounds, interval highlights; never execute algorithm code |
| graph_network | vertices and explicit edges; traversal only along supplied edges |
| coordinate_plane | reviewed axes/scales and supplied points; no expression evaluation |
| comparison | side-by-side quantities or states; preserve declared ordering |
| code_walkthrough | source code/state/output bindings, existing narration beats |

Layout is a semantic family hint. Objects/relationships remain authoritative;
layout does not introduce implicit geometry, connectors, cycles or actions.
Legacy title/recap/formula scenes remain legacy. No title keyword dispatch is
required: unknown topics use the same primitives, or explicit safe fallback.

## Relationships

`{kind,source,target}` supports connected_to,contains,points_toward,aligned_with,
before,ordered_with,belongs_to,depends_on. They describe topology/constraints,
not simulation rules. connected_to is undirected; points_toward is directed;
before is semantic ordering (not new timing); ordered_with preserves source-to-target
order in an array/sequence; aligned_with requests a shared alignment;
depends_on is conceptual dependency; contains/belongs_to provide inverse
containment constraints. No implied movement, force or chemical change.

Explicit line/arrow/path objects provide drawable connectors. **Do not draw an
additional arrow for every relationship**. The intent compiler creates linkN
objects for connected_to/points_toward and reserves their IDs; it stores the
relationship separately. Human-authored fixtures may provide curved paths.

## Six action types and exact timing

Every action: id,target,beat_id,start,end. Fractions satisfy0<=start<end<=1;
defaults start0/end.6. At most64 actions per scene and256 per lesson. Target
must exist and beat must be valid in this canonical scene.

For actual beat interval [B,E):
`A=B+start*(E-B)`, `Z=B+end*(E-B)`; progress=`clamp((absoluteFrame-A)/(Z-A),0,1)`.
Retain fractional boundaries; use the same math in browser and Remotion.
Inside Sequence convert relative frame to absolute once. No fixed seconds,
wall-clock animation, randomness, timers, audio-duration guesses or CSS animation.

| kind | Parameters/defaults | State channels |
|---|---|---|
| reveal | from_opacity0,to_opacity1 | opacity |
| draw | from_progress0,to_progress1; only line/arrow/path | stroke progress |
| move | from_position,to_position | position |
| highlight | from_style primary,to_style highlight | semantic style |
| transform | from_scale1,to_scale.75 (each .25..1); from/to_opacity1 | scale and opacity |
| trace | path_id,from_progress0,to_progress1; target marker,path target path | marker position |

All numeric transitions use clamped **linear interpolation**, including opacity,
position, scale and draw amount. Styles resolve to renderer theme tokens and
interpolate their colors linearly. Transform scales around the object's static
bounding-box center, or current position after move. Rotation and expansion
above1 are intentionally unsupported. Move positions are absolute centers,
not relative offsets; both endpoint extents must fit. Trace cannot simultaneously
write position with move. Its marker radius must fit the path's entire hull.

For draw use stroke-dashoffset / pathLength1. Arrowhead appears when progress1.
For trace progress means **pixel arc-length fraction**, after coordinate mapping.
Proposed reproducible method: line segments exact; subdivide each cubic at32
equal parameter intervals, concatenate points, then linearly locate distance
on this polyline. Use this same bounded lookup in browser and MP4. This
sampling choice requires Varun's feasibility confirmation; if changed, bump
semantics_version jointly before production. No getTotalLength dependence on
different hidden DOM layouts, and no native physics engine.

## Start/end states, conflicts and seeking

Evaluate from declarative data at ANY frame, including backwards seeks and
parallel out-of-order render frames. For each object's property channel:

1. No actions: use static default (opacity1,scale1,style from object,stroke1,
   position from object). Particles have fixed explicit positions, no random seed.
2. Before first action on that channel: hold its declared from-state.
3. During action: interpolate from-state to to-state.
4. After action: hold its final state through gaps, later beats and scene tail.
5. Next action on the channel must begin from the previous held final state.

Actions may run on independent channels together. Overlapping writes to the same
channel are rejected. Non-overlapping discontinuities are also rejected. Group
animation is rejected to avoid hidden parent/child state conflicts. No state
resets at beat boundaries. Not every object should move through an entire beat.

## Semantic style tokens

primary,secondary,accent,muted,warning,highlight. Renderer maps them to the
existing theme with legible contrast; final colors are Varun's proposed choice.
No arbitrary CSS, font names, color strings, URLs or model-supplied theme.
Highlight is emphasis, not an assertion of correctness or a red/green test result.

## Validation, limits and safe fallback

Max6 scenes;48 objects,64 relationships,64 actions per scene;128 total drawable
primitive instances per scene including particles;12 polygon vertices;8 path
segments;32 particles per collection;16 group children;max3 containment edges
of nesting;160-code-point plain text fields;512KB candidate envelope.
Source code text alone may contain up to760 chars to fit existing source limits.
All geometry/actions finite and bounded. No missing/self refs, duplicate IDs,
multiple containment parents, containment cycles, unknown kinds/properties,
unsupported style tokens, markup, paths, URLs or unapproved assets.

Fallback: `layout=null,accuracy=legacy,objects=[],relationships=[],actions=[],
fallback={code,reason}`. Existing lesson/renderer remains playable. Codes:
legacy_scene,unsupported_mechanism,source_inaccurate,invalid_candidate,
model_unavailable,not_selected,cache_invalid. Never display invalid specialized
data just because other scenes validated. Whole-envelope source mismatch returns
spec=null diagnostics; planner can produce an explicit all-legacy decision.
The source lesson is never rewritten by VQ1.

Illustrative accuracy requires a nonempty limitations list. This acknowledges
uncertainty; it does not prove correctness. No optical refraction, chemical
simulation, numerical integrator or algorithm execution is implemented. A future
reviewed deterministic geometry module needs tests and a semantics-version bump.

## Assets and licences

Approved manifest is empty, so asset objects are rejected. sun_icon/cloud_icon/
plant_icon are **provisional names**, not files or licence claims. Varun may use
existing primitives immediately; no illustrations are required to begin.
Before enabling an asset: supply local file, verify licence/attribution, record
in docs/licenses.md, approve manifest ID, bump version, add validation/tests.
Never accept an arbitrary path/URL in a spec. No new dependencies/models/fonts
were introduced by this backend milestone.

## Fixture inventory and expected behavior

| Fixture | Representation / narrated behavior | Limits |
|---|---|---|
| water_cycle | spatial sun/reservoir/cloud; parcel traces up at evaporation; cloud reveal, rain draw, reservoir highlight | qualitative phase-change diagram, source repetition retained |
| concave_lens | explicit legacy fallback | no verified refraction solver; cached myopia text incorrect |
| binary_search | inert source code/state; legacy inconsistent worked example | cached line refs and array comparisons incorrect |
| array_grid_demo | five ordered cells1,3,5,7,9; midpoint5 highlight; interval7,9 reveal; found7 highlight | synthetic corrected demonstration, separate identity |
| python_for_loop | inert source code/state, supplied-output emphasis at source beats | no code execution or inferred output |
| newtons_second_law | legacy formula; force arrow then illustrative cart displacement | not a calculated acceleration trajectory |
| photosynthesis | leaf, light, energy arrow, products arrow; beat-aligned inputs/outputs | no molecule-level transformation |
| graph_traversal | A/B/C nodes, two edges, marker follows reviewed route | authored A-B-C path, not a computed traversal |
| mathematical_function | axes and five y=x+1 points, draw at relevant beat | authored domain x0..4,y0..6; no arbitrary functions |
| heldout_velocity | reference point and direction arrow, comparison | authored vocabulary check, not model acceptance |
| heldout_area | circle and radius-direction arrow | authored geometry sketch, no area derivation |
| heldout_matter | fixed particles in solid/liquid/gas comparison | schematic, not a molecular simulation |
| heldout_heart / heldout_methane | explicit legacy fallback | no reviewed anatomy/reaction construction |

Fixtures are feasible using rect,circle,ellipse,line,polygon,path,escaped text,
flat grouping, reusable markers and limited lists. No physics engine, canvas
framework, external image service or large asset collection is needed. This is
a feasibility assessment, not evidence of an implemented frontend. Read each
fixture's origin and review_notes; source data can be scientifically wrong.
Real model results and held-out evaluation are in `scratch/vq1/acceptance.json`
and summarized in vq1-backend-status.md; authored fixtures must not be counted
as real inference successes.

**Quality gate failed:** initial visual-p1 fell back4/4; visual-p2 produced weak
label diagrams. The saved p2 outputs were recompiled with deterministic placement
(no new inference), now structurally valid, but both Water Cycle and Ohm's Law
still fail meaningful-mechanism review. See `scratch/vq1/p2/acceptance.json` and
`scratch/vq1/replay.json`. Do not treat structural validity as VQ1 completion or
wire this into production. Discuss a smaller compositional intent vocabulary
and demonstrate semantic improvement before activating model-generated visuals.

## Suggested TypeScript/component structure (frontend proposal)

Mirror the JSON Schema as strict discriminated unions (never any). For example:

```ts
type Point = {x: number; y: number};
type Label = {kind: 'source'; field: SourceField; step_index: number | null}
           | {kind: 'literal'; text: string};
type Action = Reveal | Draw | Move | Highlight | Transform | Trace;
// Each branch has its exact schema properties; no permissive index signatures.
```

Suggested modules: VisualScene (dispatch/fallback), primitives (typed object
drawers), layout (relationships and bounded placement), actions (pure property
evaluation), paths (typed segments/arc lookup), labels (localized source binding).
Precompute geometry and path samples once per scene. Per frame only evaluate
small bounded state changes. Keep existing caption/audio/chrome components.
Do not add VisualSpec fields to production RenderProps silently; agree on an
optional extension or external lookup and version its schema jointly.

## Objective frontend acceptance

- Each primitive and six actions renders in browser and MP4 with identical
  sampled state at start/middle/end, including backwards/random frame seeking.
- At least spatial,array,graph,process and explicit legacy fixtures work.
- Content remains within safe region, captions stay unobscured, Indic labels
  fit with local fonts and no missing glyphs/clipping at1280x720.
- Object/action/beat IDs map correctly; en/hi/kn use same spec with different
  measured frames; no animation starts before its referenced beat fraction.
- Held final state persists through silence/tail; channel conflict fixtures
  are rejected before rendering, not guessed away by frontend.
- Fallback renders original scene; original lesson/audio/timeline/MP4 cache
  still works if VQ1 is absent/invalid. No claim that fallback repairs bad content.
- No URL fetch, dynamic code execution, inline markup, random placement,
  wall-clock animation or CSS transition. Use only approved local assets/fonts.
- Phone/CPU-throttled browser playback and actual MP4 performance measured;
  no claim that backend tests establish renderer performance.
- Subject review of representative visuals, especially optics/math/chemistry,
  precedes an educational-quality acceptance claim.

## Integration and cache guidance — future joint work

Semantic cache: cache/visuals/key.json, independent of lesson/audio/export.
Future rendered-media cache MUST include validated visual-spec checksum,
renderer build/source fingerprint, font/asset manifest versions, timeline,
localized text and render options. Current props.sha1 lacks a renderer-build
fingerprint; VQ1 does not modify it or delete old MP4s. Use a new media cache
identity/version when production integration is approved, preserving old media.

Implementation order for Varun: confirm this contract and limits; implement
primitives/label bindings; pure six-action evaluator; water/array/graph fixtures;
Indic typography/collisions; shared browser/Remotion QA; performance checks;
then agree on optional production integration and cache versioning. Before
freezing: confirm content region/radius scaling, particle/group behavior,
arc-length sampling, slot/collision rules, fallback ownership, supplemental
translation policy and renderer-build cache identity with Satwik.

## VQ1.1 clarification — SemanticIntent and deterministic composition

This is an append-only backend clarification. **VisualSpec v1 JSON Schema,
object/action vocabulary, interpolation, coordinate system and production props
are unchanged.** Original authored examples remain valid. Frontend still needs
the same primitive interpreter; do not add a SemanticIntent interpreter to React.

The new backend-only `semantic.schema.json` is under backend/app/visuals/.
`SemanticIntent` is a discriminated family union: array_grid,spatial,
graph_network,unsupported. It contains no shapes, slots, coordinates, styles,
keyframes or durations. Source quotes are checked against canonical scene text;
change quotes must belong to their referenced narration beat. Step/intro identity
and measured timeline binding are unchanged. A quotation match is evidence of
source grounding, not proof that a scientific interpretation is true.

Use `plan_semantic_visuals` for the VQ1.1 sidecar. Existing `plan_visuals` defaults
to legacy intent for compatibility. The development CLI defaults to SemanticIntent;
`--legacy-intent` explicitly selects the previous shape/slot planner. Both remain
outside production jobs. New prompt visual-semantic-p1, intent semantic-intent-v1
and composer semantic-composer-v1 enter the independent cache key/provenance.
The validator accepts the known legacy and semantic producer pairs, with full
source/schema/reference revalidation. Old cached/fixture files are not migrated
or invalidated merely to enable this optional producer.

Deterministic capabilities:

- **Arrays:**2..8 explicitly stated unique integer values (absolute value<=100000),
  cells and fixed index labels, low/high pointers, current selection, contiguous
  narrowing ranges, numerically checked comparisons and explicit pairwise swaps.
  Model identifies values; backend derives indexes. Source ranges must be stated
  in the corresponding beat. No guessed data from code, implicit range calls,
  duplicate-value disambiguation or general algorithm execution. A current marker
  is hidden when its value leaves the active range and restored on new selection.
  Swaps move value objects, never index labels; linear swap paths may overlap
  transiently and require renderer readability review. Swapping during narrowed
  range state is rejected. False comparisons/absent middle elements fail closed.
- **Spatial:**2..6 grounded entities. Reusable primitive motifs for energy source,
  reservoir, cloud, material, plant, body, container, barrier, electrical source,
  resistor and force application point. These are component-level compositions,
  not hardcoded lesson animations or new licensed assets. Physical source quotes
  must fit the selected entity category. Closed asset_category values are metadata;
  no asset file is assumed and the approved asset manifest remains empty.
  Relations describe above/below/left/right, flow, heating, connection or push/pull.
  Static motifs and directional connections may explain a relationship without
  continuous animation. Declared flows plus beat-grounded transfer events produce
  material markers/traces. Paths are qualitative, not physical simulations.
  Cloud/water/energy have recognizable geometry rather than process sentence boxes.
- **Graphs:**2..6 nodes,<=8 explicit directed/undirected edges,2..6 grounded visits.
  Node arrangement is deterministic. Visited nodes retain emphasis; a separate
  current marker follows declared edges in source order. Arc fractions use pixel
  length, consistent with existing trace semantics. No BFS/DFS/code execution or
  fabricated edge/visit. Internal vertex IDs are namespaced by deterministic index
  to avoid collision with current/walk helper IDs.
- **Coordinate generation:**deferred. Existing authored linear_points fixtures
  remain usable; automatic domain, units and scale grounding need review. No
  symbolic-math engine, optics solver or reaction simulator was added.

Events on the same beat divide its first80% into equal ordered intervals; an
event may update independent channels together. This is deterministic beat-relative
timing, not an animation quota. Existing state validation enforces held final
values and prevents overlapping writes. Graph marker fractions represent actual
path length; array movement uses absolute cell positions.

Generated source-evidence labels are plain literal English because narration
substrings are not part of the existing SourceText reference vocabulary. Existing
`resolve_labels` warns for supplemental non-English labels. VQ1.1 does not change
Task6 translation or language approvals. Agree on reviewed label localization
before multilingual production use; no shared-schema expansion is silently implied.

Consumable fixtures: `backend/tests/fixtures/visuals_v11/` contains source, authored
intent, validated spec, origin and review notes. Water Cycle, array_bounds and
graph_traversal show the three positive composition families. concave_lens and
binary_search_cached show explicit safe fallback. ohms_law is intentionally
**partial**: recognizable source/resistor connection, not a closed circuit or
quantitative law. heldout_settling and heldout_swap exercise reusable composers
on authored unrelated mechanisms. These are authored tests, not real-model passes.
No Ollama run is needed for Varun to consume their VisualSpec objects.

Frontend next tasks: confirm existing v1 primitive/state semantics; render the
spatial motifs and source-grounded transfer traces; implement array bound/current
markers and visited/current graph behavior; test random seeks and held states;
review collisions/text fitting (including swap paths), English supplemental labels
in Indic lessons, browser/MP4 parity and CPU playback. The frontend renderer and
production integration still require joint approval. No new renderer wire-contract
fields or breaking migrations are proposed by VQ1.1.

VQ1.1 real-model gate remains **FAILED**:6 genuine CPU calls across cached Water
Cycle,Binary Search and held-out Photosynthesis produced3 safe fallbacks, not
accepted specialized explanations. The new authored fixtures are usable for
renderer development, but are not evidence that the 4B model is production-ready.
Read scratch/vq11/evaluation.json and the status checkpoint before planning
integration. No further prompt loop was run and no production sidecar was enabled.
