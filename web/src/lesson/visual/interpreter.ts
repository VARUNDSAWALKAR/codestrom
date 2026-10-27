import type {TimelineScene} from '../types';
import {parseVisualSpec} from './parse';
import type {VisualPrimitive, VisualSpec} from './types';

function visit(primitives: readonly VisualPrimitive[], callback: (primitive: VisualPrimitive) => void): void {
  for (const primitive of primitives) {
    callback(primitive);
    if (primitive.type === 'group') visit(primitive.children, callback);
  }
}

/** Parses untrusted JSON and binds every visual trigger to a real narration beat. */
export function interpretVisualSpec(value: unknown, timelineScene: TimelineScene): VisualSpec {
  const spec = parseVisualSpec(value);
  const beats = new Set(timelineScene.beats.map((beat) => beat.beat_id));
  visit(spec.primitives, (primitive) => {
    for (const action of primitive.actions ?? []) {
      if (!beats.has(action.beatId)) throw new Error(`Visual action references unknown beat ${action.beatId}`);
    }
  });
  for (const [beatId, lines] of Object.entries(spec.code?.activeLines ?? {})) {
    if (!beats.has(beatId)) throw new Error(`Code highlight references unknown beat ${beatId}`);
    const lineCount = spec.code?.source.split('\n').length ?? 0;
    if (lines.some((line) => line > lineCount)) throw new Error(`Code highlight for ${beatId} is outside the source`);
  }
  return spec;
}

