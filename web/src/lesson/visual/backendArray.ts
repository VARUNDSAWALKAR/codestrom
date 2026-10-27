/** Narrow visual-v1 adapter. The existing backend wire types remain authoritative. */
import {interpolateColors} from 'remotion';
import {parseVisualSpec} from '../../utils/parseVisualSpec';
import type {HighlightRegionObject, HighlightVisualAction, RectangleObject, RevealVisualAction,
  TextObject, VisualStyle} from '../../types/visualSpec';
import type {RenderProps, Scene, TimelineScene} from '../types';
import {parseRenderProps} from '../validate';
import {theme} from '../theme';

type ArrayObject = RectangleObject | TextObject | HighlightRegionObject;
type ArrayAction = RevealVisualAction | HighlightVisualAction;
export interface ArrayEvent {action: ArrayAction; start: number; end: number}
export interface PreparedArray {
  sceneId: string; language: RenderProps['lesson']['language']; timelineScene: TimelineScene;
  objects: ArrayObject[]; labels: Map<string, string>; events: ArrayEvent[];
}

export const arrayPalette: Record<VisualStyle, {fill: string; stroke: string}> = {
  primary: {fill: theme.surface, stroke: theme.ink2},
  secondary: {fill: theme.bg, stroke: theme.ink2},
  accent: {fill: theme.accentSoft, stroke: theme.accent},
  muted: {fill: theme.bg, stroke: theme.line},
  warning: {fill: theme.surface, stroke: theme.parts[2]},
  highlight: {fill: theme.accentSoft, stroke: theme.accent},
};

function sourceLabel(object: ArrayObject, scene: Scene): string | null {
  const label = object.label;
  if (!label) return null;
  if (label.kind === 'literal') return label.text;
  const source = label.step_index === null ? scene : scene.steps[label.step_index];
  if (!source || !(label.field in source)) throw new Error('Missing source label field');
  const value = (source as unknown as Record<string, unknown>)[label.field];
  if (typeof value !== 'string' || value.length > 160 || /[\r\n]/u.test(value)) throw new Error('Unsupported label text');
  return value;
}

export function arrayBox(object: ArrayObject) {
  const width = object.width * 1152, height = object.height * 460;
  return {x: 64 + object.position.x * 1152 - width / 2,
    y: 120 + object.position.y * 460 - height / 2, width, height};
}

export function prepareArrayScene(value: unknown, props: RenderProps, sceneId: string): PreparedArray {
  parseRenderProps(props);
  const spec = parseVisualSpec(value); // Enforces visual_schema_version and strict backend fields.
  const source = props.lesson.scenes.find((scene) => scene.id === sceneId);
  const time = props.timeline.scenes.find((scene) => scene.scene_id === sceneId);
  if (!source || source.type !== 'diagram' || !time || spec.lesson_id !== props.lesson.lesson_id ||
      spec.scenes.length !== props.lesson.scenes.length ||
      spec.scenes.some((scene, index) => scene.scene_id !== props.lesson.scenes[index]?.id)) throw new Error('Source/visual identity mismatch');
  if (props.lesson.language !== 'en') throw new Error('This reviewed slice requires canonical English labels');
  const provenance = spec.provenance;
  if (provenance.capability_version !== 'primitives-v1' || provenance.asset_version !== 'assets-v1-empty' ||
      provenance.semantics_version !== 'geometry-actions-v2') throw new Error('Unsupported visual semantics version');
  const scene = spec.scenes.find((item) => item.scene_id === sceneId);
  if (!scene || scene.fallback || scene.layout !== 'array_grid') throw new Error('Legacy or unsupported visual scene');
  if (scene.objects.some((object) => !['rectangle', 'text', 'highlight_region'].includes(object.kind))) throw new Error('Unsupported array object');
  const objects = scene.objects as ArrayObject[];
  const byId = new Map(objects.map((object) => [object.id, object]));
  const labels = new Map<string, string>();
  for (const object of objects) {
    const box = arrayBox(object);
    if (box.x < 64 || box.y < 120 || box.x + box.width > 1216 || box.y + box.height > 580) throw new Error('Object outside content bounds');
    const label = sourceLabel(object, source);
    if (label !== null) labels.set(object.id, label);
  }
  // No implicit connectors or re-layout. Groups and containment are outside this slice.
  for (const edge of scene.relationships) {
    const a = byId.get(edge.source), b = byId.get(edge.target);
    if (edge.kind !== 'ordered_with' || !a || !b || a.position.x >= b.position.x) throw new Error('Unsupported or inconsistent array relationship');
  }
  const beatIds = new Set<string>();
  for (const beat of time.beats) {
    const expected = beat.step_index === null ? `${sceneId}.intro` : `${sceneId}.step${beat.step_index}`;
    if (beat.beat_id !== expected || beatIds.has(beat.beat_id)) throw new Error('Invalid scene-local narration beat');
    beatIds.add(beat.beat_id);
  }
  const events: ArrayEvent[] = scene.actions.map((action) => {
    if (action.kind !== 'reveal' && action.kind !== 'highlight') throw new Error('Unsupported array action');
    const beat = time.beats.find((item) => item.beat_id === action.beat_id);
    if (!beat) throw new Error('Missing narration beat');
    const duration = beat.end_frame - beat.start_frame;
    return {action, start: beat.start_frame + action.start * duration, end: beat.start_frame + action.end * duration};
  }).sort((a, b) => a.start - b.start || a.end - b.end);
  for (const object of objects) {
    for (const kind of ['reveal', 'highlight'] as const) {
      const channel = events.filter((event) => event.action.target === object.id && event.action.kind === kind);
      for (let i = 1; i < channel.length; i++) {
        const previous = channel[i - 1]!, next = channel[i]!;
        if (previous.end > next.start) throw new Error('Overlapping property channel');
        if (previous.action.kind === 'reveal' && next.action.kind === 'reveal' && previous.action.to_opacity !== next.action.from_opacity ||
            previous.action.kind === 'highlight' && next.action.kind === 'highlight' && previous.action.to_style !== next.action.from_style) throw new Error('Discontinuous property channel');
      }
    }
  }
  return {sceneId, language: props.lesson.language, timelineScene: time, objects, labels, events};
}

/** Clamped linear channels, evaluated independently at any absolute frame. */
export function arrayObjectState(prepared: PreparedArray, object: ArrayObject, frame: number) {
  let opacity = 1;
  let colors = arrayPalette[object.style];
  for (const kind of ['reveal', 'highlight'] as const) {
    for (const event of prepared.events.filter((entry) => entry.action.target === object.id && entry.action.kind === kind)) {
      const amount = Math.max(0, Math.min(1, (frame - event.start) / (event.end - event.start)));
      const action = event.action;
      if (action.kind === 'reveal') opacity = action.from_opacity + amount * (action.to_opacity - action.from_opacity);
      else {
        const from = arrayPalette[action.from_style], to = arrayPalette[action.to_style];
        colors = {fill: interpolateColors(amount, [0, 1], [from.fill, to.fill]), stroke: interpolateColors(amount, [0, 1], [from.stroke, to.stroke])};
      }
      if (frame < event.end) break; // Earlier final state persists until the next channel interval.
    }
  }
  return {opacity, ...colors};
}
