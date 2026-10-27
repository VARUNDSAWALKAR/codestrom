import type {
  AssetObject, BoundVisualAction, CircleObject, CubicPathSegment, DrawVisualAction, EllipseObject,
  FallbackSceneVisual, GroupObject, HighlightRegionObject, HighlightVisualAction, LineObject,
  LinePathSegment, MarkerObject, MoveVisualAction, NarrationBeat, ParticlesObject, PathObject,
  PolygonObject, RectangleObject, RevealVisualAction, SceneVisual, SpecializedSceneVisual, TextObject,
  TraceVisualAction, TransformVisualAction, VisualAction, VisualFallback, VisualFixture,
  VisualFixtureExpectation, VisualFixtureLesson, VisualFixtureScene, VisualFixtureStep, VisualLabel,
  VisualObject, VisualPoint, VisualProvenance, VisualRelationship, VisualSpec, VisualStyle, VisualTimeline,
} from '../types/visualSpec';

type Obj = Record<string, unknown>;
const idPattern = /^[a-z][a-z0-9_-]{0,31}$/;
const scenePattern = /^s[1-9][0-9]*$/;
const beatPattern = /^s[1-9][0-9]*\.(?:intro|step[0-5])$/;
const digestPattern = /^[0-9a-f]{64}$/;
const styles = ['primary', 'secondary', 'accent', 'muted', 'warning', 'highlight'] as const;
const layouts = ['flow_cycle', 'spatial', 'array_grid', 'graph_network', 'coordinate_plane', 'comparison', 'code_walkthrough'] as const;
const relationshipKinds = ['connected_to', 'contains', 'points_toward', 'aligned_with', 'before', 'ordered_with', 'belongs_to', 'depends_on'] as const;
const fallbackCodes = ['legacy_scene', 'unsupported_mechanism', 'source_inaccurate', 'invalid_candidate', 'model_unavailable', 'not_selected', 'cache_invalid'] as const;
const languages = ['en', 'hi', 'kn', 'ta', 'te', 'bn', 'mr'] as const;

function object(value: unknown, name: string): Obj {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${name} must be an object`);
  return value as Obj;
}
function strict(raw: Obj, allowed: readonly string[], name: string): void {
  const extra = Object.keys(raw).find((key) => !allowed.includes(key));
  if (extra) throw new Error(`${name} contains unknown field ${extra}`);
}
function list(value: unknown, name: string, min = 0, max = Infinity): unknown[] {
  if (!Array.isArray(value) || value.length < min || value.length > max) throw new Error(`${name} must contain ${min}–${max} items`);
  return value;
}
function string(value: unknown, name: string, min = 0, max = Infinity): string {
  if (typeof value !== 'string' || value.length < min || Array.from(value).length > max) throw new Error(`${name} must be a string of length ${min}–${max}`);
  return value;
}
function text(value: unknown, name: string): string {
  const result = string(value, name, 1, 160);
  if (/<\s*[\/? !a-z]/i.test(result) || /[a-z][a-z0-9+.-]*:\/\//i.test(result) || /(?:data|javascript|file):/i.test(result) || /\\\\|dangerouslySetInnerHTML|\b(?:eval|exec|compile|__import__|subprocess)\s*\(/i.test(result) || Array.from(result).some((character) => character.charCodeAt(0) < 32)) throw new Error(`${name} contains unsafe text`);
  return result;
}
function finite(value: unknown, name: string, min = -Infinity, max = Infinity): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) throw new Error(`${name} must be between ${min} and ${max}`);
  return value;
}
function integer(value: unknown, name: string, min = -Infinity, max = Infinity): number {
  const result = finite(value, name, min, max); if (!Number.isSafeInteger(result)) throw new Error(`${name} must be an integer`); return result;
}
function bool(value: unknown, name: string): boolean {if (typeof value !== 'boolean') throw new Error(`${name} must be boolean`); return value;}
function enumValue<T extends string>(value: unknown, choices: readonly T[], name: string): T {
  if (typeof value !== 'string' || !choices.includes(value as T)) throw new Error(`Invalid ${name}`); return value as T;
}
function pattern(value: unknown, regex: RegExp, name: string): string {const result = string(value, name, 1); if (!regex.test(result)) throw new Error(`Invalid ${name}`); return result;}
function nullable<T>(value: unknown, parser: (entry: unknown) => T): T | null {return value === null || value === undefined ? null : parser(value);}

function point(value: unknown, name: string): VisualPoint {
  const raw = object(value, name); strict(raw, ['x', 'y'], name);
  return {x: finite(raw.x, `${name}.x`, 0, 1), y: finite(raw.y, `${name}.y`, 0, 1)};
}
function label(value: unknown, name: string): VisualLabel {
  const raw = object(value, name); const kind = enumValue(raw.kind, ['source', 'literal'], `${name}.kind`);
  if (kind === 'literal') {strict(raw, ['kind', 'text'], name); return {kind, text: text(raw.text, `${name}.text`)};}
  strict(raw, ['kind', 'field', 'step_index'], name);
  const field = enumValue(raw.field, ['heading', 'center', 'expression', 'code', 'text', 'note', 'output'], `${name}.field`);
  const stepIndex = raw.step_index === null || raw.step_index === undefined ? null : integer(raw.step_index, `${name}.step_index`, 0, 5);
  if (['text', 'note', 'output'].includes(field) !== (stepIndex !== null)) throw new Error(`${name} source field has invalid step_index`);
  return {kind, field, step_index: stepIndex};
}
function base(raw: Obj, name: string) {
  return {id: pattern(raw.id, idPattern, `${name}.id`), role: text(raw.role, `${name}.role`),
    style: (raw.style === undefined ? 'primary' : enumValue(raw.style, styles, `${name}.style`)) as VisualStyle,
    label: nullable(raw.label, (value) => label(value, `${name}.label`))};
}
const baseKeys = ['id', 'role', 'style', 'label', 'kind'] as const;
function visualObject(value: unknown, name: string): VisualObject {
  const raw = object(value, name); const kind = enumValue(raw.kind, ['rectangle', 'circle', 'ellipse', 'polygon', 'line', 'arrow', 'path', 'text', 'group', 'marker', 'highlight_region', 'particles', 'asset'], `${name}.kind`);
  const common = base(raw, name);
  if (kind === 'rectangle') {strict(raw, [...baseKeys, 'position', 'width', 'height'], name); return {...common, kind, position: point(raw.position, `${name}.position`), width: finite(raw.width, `${name}.width`, Number.MIN_VALUE, 1), height: finite(raw.height, `${name}.height`, Number.MIN_VALUE, 1)} satisfies RectangleObject;}
  if (kind === 'circle') {strict(raw, [...baseKeys, 'position', 'radius'], name); return {...common, kind, position: point(raw.position, `${name}.position`), radius: finite(raw.radius, `${name}.radius`, Number.MIN_VALUE, .5)} satisfies CircleObject;}
  if (kind === 'ellipse') {strict(raw, [...baseKeys, 'position', 'rx', 'ry'], name); return {...common, kind, position: point(raw.position, `${name}.position`), rx: finite(raw.rx, `${name}.rx`, Number.MIN_VALUE, .5), ry: finite(raw.ry, `${name}.ry`, Number.MIN_VALUE, .5)} satisfies EllipseObject;}
  if (kind === 'polygon') {strict(raw, [...baseKeys, 'points'], name); const points = list(raw.points, `${name}.points`, 3, 12).map((item, index) => point(item, `${name}.points[${index}]`)); return {...common, kind, points} satisfies PolygonObject;}
  if (kind === 'line' || kind === 'arrow') {strict(raw, [...baseKeys, 'start', 'end'], name); const start = point(raw.start, `${name}.start`); const end = point(raw.end, `${name}.end`); if (start.x === end.x && start.y === end.y) throw new Error(`${name} cannot have zero length`); return {...common, kind, start, end} satisfies LineObject;}
  if (kind === 'path') {
    strict(raw, [...baseKeys, 'start', 'segments'], name); const start = point(raw.start, `${name}.start`);
    const segments = list(raw.segments, `${name}.segments`, 1, 8).map((item, index): LinePathSegment | CubicPathSegment => {
      const segment = object(item, `${name}.segments[${index}]`); const segmentKind = enumValue(segment.kind, ['line', 'cubic'], `${name}.segments[${index}].kind`);
      if (segmentKind === 'line') {strict(segment, ['kind', 'end'], `${name}.segments[${index}]`); return {kind: segmentKind, end: point(segment.end, `${name}.segments[${index}].end`)};}
      strict(segment, ['kind', 'control1', 'control2', 'end'], `${name}.segments[${index}]`); return {kind: segmentKind, control1: point(segment.control1, `${name}.segments[${index}].control1`), control2: point(segment.control2, `${name}.segments[${index}].control2`), end: point(segment.end, `${name}.segments[${index}].end`)};
    }); return {...common, kind, start, segments} satisfies PathObject;
  }
  if (kind === 'text') {strict(raw, [...baseKeys, 'position', 'width', 'height'], name); if (!common.label) throw new Error(`${name}.label is required`); return {...common, kind, label: common.label, position: point(raw.position, `${name}.position`), width: finite(raw.width ?? .25, `${name}.width`, Number.MIN_VALUE, 1), height: finite(raw.height ?? .12, `${name}.height`, Number.MIN_VALUE, 1)} satisfies TextObject;}
  if (kind === 'group') {strict(raw, [...baseKeys, 'children'], name); return {...common, kind, children: list(raw.children, `${name}.children`, 1, 16).map((item, index) => pattern(item, idPattern, `${name}.children[${index}]`))} satisfies GroupObject;}
  if (kind === 'marker') {strict(raw, [...baseKeys, 'position', 'radius'], name); return {...common, kind, position: point(raw.position, `${name}.position`), radius: finite(raw.radius ?? .008, `${name}.radius`, Number.MIN_VALUE, .02)} satisfies MarkerObject;}
  if (kind === 'highlight_region') {strict(raw, [...baseKeys, 'position', 'width', 'height'], name); return {...common, kind, position: point(raw.position, `${name}.position`), width: finite(raw.width, `${name}.width`, Number.MIN_VALUE, 1), height: finite(raw.height, `${name}.height`, Number.MIN_VALUE, 1)} satisfies HighlightRegionObject;}
  if (kind === 'particles') {strict(raw, [...baseKeys, 'positions', 'radius'], name); return {...common, kind, positions: list(raw.positions, `${name}.positions`, 1, 32).map((item, index) => point(item, `${name}.positions[${index}]`)), radius: finite(raw.radius ?? .005, `${name}.radius`, Number.MIN_VALUE, .02)} satisfies ParticlesObject;}
  strict(raw, [...baseKeys, 'asset_id', 'position', 'width', 'height'], name);
  const asset = {...common, kind, asset_id: pattern(raw.asset_id, idPattern, `${name}.asset_id`), position: point(raw.position, `${name}.position`), width: finite(raw.width, `${name}.width`, Number.MIN_VALUE, 1), height: finite(raw.height, `${name}.height`, Number.MIN_VALUE, 1)} satisfies AssetObject;
  throw new Error(`${name} references asset ${asset.asset_id}, but the approved asset manifest is empty`);
}

const actionBaseKeys = ['id', 'target', 'beat_id', 'start', 'end', 'kind'] as const;
function action(value: unknown, name: string): VisualAction {
  const raw = object(value, name); const kind = enumValue(raw.kind, ['reveal', 'draw', 'move', 'highlight', 'transform', 'trace'], `${name}.kind`);
  const start = finite(raw.start ?? 0, `${name}.start`, 0, 1); const end = finite(raw.end ?? .6, `${name}.end`, 0, 1); if (start >= end) throw new Error(`${name} has an empty interval`);
  const common = {id: pattern(raw.id, idPattern, `${name}.id`), target: pattern(raw.target, idPattern, `${name}.target`), beat_id: pattern(raw.beat_id, beatPattern, `${name}.beat_id`), start, end};
  if (kind === 'reveal') {strict(raw, [...actionBaseKeys, 'from_opacity', 'to_opacity'], name); return {...common, kind, from_opacity: finite(raw.from_opacity ?? 0, `${name}.from_opacity`, 0, 1), to_opacity: finite(raw.to_opacity ?? 1, `${name}.to_opacity`, 0, 1)} satisfies RevealVisualAction;}
  if (kind === 'draw') {strict(raw, [...actionBaseKeys, 'from_progress', 'to_progress'], name); return {...common, kind, from_progress: finite(raw.from_progress ?? 0, `${name}.from_progress`, 0, 1), to_progress: finite(raw.to_progress ?? 1, `${name}.to_progress`, 0, 1)} satisfies DrawVisualAction;}
  if (kind === 'move') {strict(raw, [...actionBaseKeys, 'from_position', 'to_position'], name); return {...common, kind, from_position: point(raw.from_position, `${name}.from_position`), to_position: point(raw.to_position, `${name}.to_position`)} satisfies MoveVisualAction;}
  if (kind === 'highlight') {strict(raw, [...actionBaseKeys, 'from_style', 'to_style'], name); return {...common, kind, from_style: enumValue(raw.from_style ?? 'primary', styles, `${name}.from_style`), to_style: enumValue(raw.to_style ?? 'highlight', styles, `${name}.to_style`)} satisfies HighlightVisualAction;}
  if (kind === 'transform') {strict(raw, [...actionBaseKeys, 'from_scale', 'to_scale', 'from_opacity', 'to_opacity'], name); return {...common, kind, from_scale: finite(raw.from_scale ?? 1, `${name}.from_scale`, .25, 1), to_scale: finite(raw.to_scale ?? .75, `${name}.to_scale`, .25, 1), from_opacity: finite(raw.from_opacity ?? 1, `${name}.from_opacity`, 0, 1), to_opacity: finite(raw.to_opacity ?? 1, `${name}.to_opacity`, 0, 1)} satisfies TransformVisualAction;}
  strict(raw, [...actionBaseKeys, 'path_id', 'from_progress', 'to_progress'], name); return {...common, kind, path_id: pattern(raw.path_id, idPattern, `${name}.path_id`), from_progress: finite(raw.from_progress ?? 0, `${name}.from_progress`, 0, 1), to_progress: finite(raw.to_progress ?? 1, `${name}.to_progress`, 0, 1)} satisfies TraceVisualAction;
}

function relationship(value: unknown, name: string): VisualRelationship {
  const raw = object(value, name); strict(raw, ['kind', 'source', 'target'], name);
  return {kind: enumValue(raw.kind, relationshipKinds, `${name}.kind`), source: pattern(raw.source, idPattern, `${name}.source`), target: pattern(raw.target, idPattern, `${name}.target`)};
}
function fallback(value: unknown, name: string): VisualFallback {
  const raw = object(value, name); strict(raw, ['code', 'reason'], name);
  return {code: enumValue(raw.code, fallbackCodes, `${name}.code`), reason: text(raw.reason, `${name}.reason`)};
}
function sceneVisual(value: unknown, name: string): SceneVisual {
  const raw = object(value, name); strict(raw, ['scene_id', 'layout', 'mechanism', 'accuracy', 'limitations', 'objects', 'relationships', 'actions', 'fallback'], name);
  const scene_id = pattern(raw.scene_id, scenePattern, `${name}.scene_id`); const mechanism = text(raw.mechanism, `${name}.mechanism`);
  const limitations = list(raw.limitations, `${name}.limitations`, 1, 6).map((item, index) => text(item, `${name}.limitations[${index}]`));
  if (raw.fallback !== null && raw.fallback !== undefined) {
    if (raw.layout !== null || raw.accuracy !== 'legacy' || list(raw.objects, `${name}.objects`).length || list(raw.relationships, `${name}.relationships`).length || list(raw.actions, `${name}.actions`).length) throw new Error(`${name} has an invalid fallback payload`);
    return {scene_id, layout: null, mechanism, accuracy: 'legacy', limitations, objects: [], relationships: [], actions: [], fallback: fallback(raw.fallback, `${name}.fallback`)} satisfies FallbackSceneVisual;
  }
  const objects = list(raw.objects, `${name}.objects`, 1, 48).map((item, index) => visualObject(item, `${name}.objects[${index}]`));
  const relationships = list(raw.relationships, `${name}.relationships`, 0, 64).map((item, index) => relationship(item, `${name}.relationships[${index}]`));
  const actions = list(raw.actions, `${name}.actions`, 1, 64).map((item, index) => action(item, `${name}.actions[${index}]`));
  const result = {scene_id, layout: enumValue(raw.layout, layouts, `${name}.layout`), mechanism, accuracy: enumValue(raw.accuracy, ['illustrative'], `${name}.accuracy`), limitations, objects, relationships, actions, fallback: null} satisfies SpecializedSceneVisual;
  validateSceneReferences(result, name); return result;
}
function validateSceneReferences(scene: SpecializedSceneVisual, name: string): void {
  const objects = new Map<string, VisualObject>(); for (const item of scene.objects) {if (objects.has(item.id)) throw new Error(`${name} has duplicate object ${item.id}`); objects.set(item.id, item);}
  const actionIds = new Set<string>();
  for (const edge of scene.relationships) if (!objects.has(edge.source) || !objects.has(edge.target) || edge.source === edge.target) throw new Error(`${name} has an invalid relationship reference`);
  for (const item of scene.objects) if (item.kind === 'group') for (const child of item.children) if (!objects.has(child) || child === item.id) throw new Error(`${name} has an invalid group child`);
  for (const item of scene.actions) {
    if (actionIds.has(item.id)) throw new Error(`${name} has duplicate action ${item.id}`); actionIds.add(item.id);
    const target = objects.get(item.target); if (!target || target.kind === 'group') throw new Error(`${name} action targets an invalid object`);
    if (item.kind === 'draw' && !['line', 'arrow', 'path'].includes(target.kind)) throw new Error(`${name} draw target is not drawable`);
    if (item.kind === 'trace' && objects.get(item.path_id)?.kind !== 'path') throw new Error(`${name} trace path is invalid`);
  }
}

function provenance(value: unknown): VisualProvenance {
  const raw = object(value, 'spec.provenance'); strict(raw, ['prompt_version', 'model', 'model_identity', 'capability_version', 'asset_version', 'semantics_version', 'configuration_fingerprint'], 'spec.provenance');
  return {prompt_version: string(raw.prompt_version, 'prompt_version', 1), model: string(raw.model, 'model', 1), model_identity: text(raw.model_identity, 'model_identity'), capability_version: string(raw.capability_version, 'capability_version', 1), asset_version: string(raw.asset_version, 'asset_version', 1), semantics_version: string(raw.semantics_version, 'semantics_version', 1), configuration_fingerprint: pattern(raw.configuration_fingerprint, digestPattern, 'configuration_fingerprint')};
}
export function parseVisualSpec(value: unknown): VisualSpec {
  const raw = object(value, 'spec'); strict(raw, ['visual_schema_version', 'lesson_id', 'source_fingerprint', 'provenance', 'scenes'], 'spec');
  if (raw.visual_schema_version !== 'visual-v1') throw new Error('Unsupported visual_schema_version');
  const scenes = list(raw.scenes, 'spec.scenes', 3, 6).map((item, index) => sceneVisual(item, `spec.scenes[${index}]`));
  if (new Set(scenes.map((scene) => scene.scene_id)).size !== scenes.length) throw new Error('Duplicate visual scene IDs');
  return {visual_schema_version: 'visual-v1', lesson_id: string(raw.lesson_id, 'spec.lesson_id', 1), source_fingerprint: pattern(raw.source_fingerprint, digestPattern, 'spec.source_fingerprint'), provenance: provenance(raw.provenance), scenes};
}

function fixtureStep(value: unknown, name: string): VisualFixtureStep {
  const raw = object(value, name); strict(raw, ['text', 'narration', 'note', 'lines', 'output', 'in_expression'], name);
  return {text: string(raw.text, `${name}.text`), narration: string(raw.narration, `${name}.narration`, 1), note: string(raw.note, `${name}.note`), lines: list(raw.lines, `${name}.lines`).map((item, index) => integer(item, `${name}.lines[${index}]`, 1)), output: string(raw.output, `${name}.output`), in_expression: bool(raw.in_expression, `${name}.in_expression`)};
}
function fixtureScene(value: unknown, name: string): VisualFixtureScene {
  const raw = object(value, name); strict(raw, ['id', 'type', 'heading', 'narration', 'steps', 'subtitle', 'code', 'code_language', 'layout', 'center', 'expression'], name);
  return {id: pattern(raw.id, scenePattern, `${name}.id`), type: enumValue(raw.type, ['title_card', 'code_walkthrough', 'diagram', 'formula', 'recap'], `${name}.type`), heading: string(raw.heading, `${name}.heading`, 1), narration: string(raw.narration, `${name}.narration`), steps: list(raw.steps, `${name}.steps`, 0, 6).map((item, index) => fixtureStep(item, `${name}.steps[${index}]`)), subtitle: string(raw.subtitle, `${name}.subtitle`), code: string(raw.code, `${name}.code`), code_language: enumValue(raw.code_language, ['python', 'javascript', 'java', 'c', 'cpp', 'other'], `${name}.code_language`), layout: enumValue(raw.layout, ['flow', 'cycle', 'labelled'], `${name}.layout`), center: string(raw.center, `${name}.center`), expression: string(raw.expression, `${name}.expression`)};
}
function fixtureLesson(value: unknown): VisualFixtureLesson {
  const raw = object(value, 'fixture.source'); strict(raw, ['schema_version', 'lesson_id', 'topic', 'level', 'target_seconds', 'language', 'source', 'model', 'prompt_version', 'warnings', 'title', 'subject', 'keep_terms', 'scenes'], 'fixture.source');
  if (raw.schema_version !== '1.0') throw new Error('Unsupported source schema');
  const scenes = list(raw.scenes, 'source.scenes', 3, 6).map((item, index) => fixtureScene(item, `source.scenes[${index}]`));
  return {schema_version: '1.0', lesson_id: string(raw.lesson_id, 'source.lesson_id', 1), topic: string(raw.topic, 'source.topic', 3, 120), level: enumValue(raw.level, ['beginner', 'intermediate'], 'source.level'), target_seconds: integer(raw.target_seconds, 'source.target_seconds', 30, 90), language: enumValue(raw.language, languages, 'source.language'), source: enumValue(raw.source, ['llm', 'fallback', 'sample', 'edited'], 'source.source'), model: string(raw.model, 'source.model'), prompt_version: string(raw.prompt_version, 'source.prompt_version'), warnings: list(raw.warnings, 'source.warnings').map((item) => string(item, 'source.warning')), title: string(raw.title, 'source.title', 1), subject: enumValue(raw.subject, ['programming', 'physics', 'chemistry', 'biology', 'math', 'other'], 'source.subject'), keep_terms: list(raw.keep_terms, 'source.keep_terms', 0, 8).map((item) => string(item, 'source.keep_term')), scenes};
}
function expectation(value: unknown): VisualFixtureExpectation {
  const raw = object(value, 'fixture.expected'); strict(raw, ['layout', 'objects', 'actions', 'specialized_scene_ids', 'fallback_scenes'], 'fixture.expected');
  return {layout: enumValue(raw.layout, layouts, 'expected.layout'), objects: integer(raw.objects, 'expected.objects', 0), actions: integer(raw.actions, 'expected.actions', 0), specialized_scene_ids: list(raw.specialized_scene_ids, 'expected.specialized_scene_ids').map((item) => pattern(item, scenePattern, 'expected.scene_id')), fallback_scenes: integer(raw.fallback_scenes, 'expected.fallback_scenes', 0)};
}
export function parseVisualFixture(value: unknown): VisualFixture {
  const raw = object(value, 'fixture'); strict(raw, ['origin', 'source', 'spec', 'expected', 'review_notes'], 'fixture');
  const source = fixtureLesson(raw.source); const spec = parseVisualSpec(raw.spec); const expected = expectation(raw.expected);
  if (source.lesson_id !== spec.lesson_id || source.scenes.length !== spec.scenes.length || source.scenes.some((scene, index) => scene.id !== spec.scenes[index]?.scene_id)) throw new Error('Fixture source/spec identity mismatch');
  const beats = new Set(source.scenes.flatMap((scene) => [...(scene.narration.trim() ? [`${scene.id}.intro`] : []), ...scene.steps.map((_, index) => `${scene.id}.step${index}`)]));
  if (spec.scenes.some((scene) => scene.actions.some((item) => !beats.has(item.beat_id)))) throw new Error('Visual action references an unknown narration beat');
  const specialized = spec.scenes.filter((scene): scene is SpecializedSceneVisual => scene.fallback === null);
  if (specialized.length !== expected.specialized_scene_ids.length || specialized.some((scene) => !expected.specialized_scene_ids.includes(scene.scene_id)) || specialized.reduce((sum, scene) => sum + scene.objects.length, 0) !== expected.objects || specialized.reduce((sum, scene) => sum + scene.actions.length, 0) !== expected.actions || spec.scenes.length - specialized.length !== expected.fallback_scenes || specialized.some((scene) => scene.layout !== expected.layout)) throw new Error('Fixture expected counts do not match spec');
  return {origin: text(raw.origin, 'fixture.origin'), source, spec, expected, review_notes: list(raw.review_notes, 'fixture.review_notes').map((item, index) => text(item, `fixture.review_notes[${index}]`))};
}

export function parseVisualSpecJson(json: string): VisualSpec {
  if (new TextEncoder().encode(json).byteLength > 512 * 1024) throw new Error('VisualSpec exceeds 512KB');
  let value: unknown; try {value = JSON.parse(json) as unknown;} catch {throw new Error('VisualSpec is not valid JSON');}
  return parseVisualSpec(value);
}

export function bindVisualActions(spec: VisualSpec, timeline: VisualTimeline): BoundVisualAction[] {
  if (spec.lesson_id !== timeline.lesson_id) throw new Error('VisualSpec/timeline identity mismatch');
  const beats = new Map<string, NarrationBeat>(timeline.scenes.flatMap((scene) => scene.beats.map((beat) => [beat.beat_id, beat] as const)));
  return spec.scenes.flatMap((scene) => scene.actions.map((item) => {
    const beat = beats.get(item.beat_id); if (!beat) throw new Error(`Missing timeline beat ${item.beat_id}`);
    const duration = beat.end_frame - beat.start_frame;
    return {scene_id: scene.scene_id, action_id: item.id, beat_id: item.beat_id,
      start_frame: beat.start_frame + item.start * duration, end_frame: beat.start_frame + item.end * duration};
  }));
}
