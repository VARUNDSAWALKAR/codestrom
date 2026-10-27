import {interpolate, interpolateColors, spring} from 'remotion';
import {theme} from '../theme';
import type {TimelineScene} from '../types';
import type {VisualAction} from './types';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export interface AnimatedPrimitiveState {
  opacity: number;
  transform: string;
  strokeDasharray?: number;
  strokeDashoffset?: number;
  stroke?: string;
  filter?: string;
}

function progress(action: VisualAction, scene: TimelineScene, frame: number, fps: number): number {
  const beat = scene.beats.find((item) => item.beat_id === action.beatId);
  if (!beat) return 0;
  const start = beat.start_frame + (action.offsetFrames ?? 0);
  const duration = action.durationFrames ?? Math.max(6, Math.round(fps * 0.32));
  return interpolate(frame, [start, start + duration], [0, 1], clamp);
}

/** Resolves every action from absolute timeline frames; deterministic under parallel rendering. */
export function resolveActions(actions: readonly VisualAction[] | undefined, scene: TimelineScene,
  absoluteFrame: number, fps: number): AnimatedPrimitiveState {
  const staged = actions?.some((action) => action.type === 'reveal' || action.type === 'draw' || action.type === 'trace') ?? false;
  let opacity = staged ? 0 : 1;
  let transform = '';
  let strokeDasharray: number | undefined;
  let strokeDashoffset: number | undefined;
  let stroke: string | undefined;
  let filter: string | undefined;
  for (const action of actions ?? []) {
    const amount = progress(action, scene, absoluteFrame, fps);
    if (action.type === 'reveal') {
      const beat = scene.beats.find((item) => item.beat_id === action.beatId);
      const start = (beat?.start_frame ?? 0) + (action.offsetFrames ?? 0);
      const duration = action.durationFrames ?? Math.max(6, Math.round(fps * .32));
      const eased = absoluteFrame < start ? 0 : absoluteFrame >= start + duration ? 1 :
        spring({frame: absoluteFrame - start, fps, durationInFrames: duration, config: {damping: 200}});
      opacity = Math.max(opacity, Math.min(1, eased));
      transform += ` scale(${interpolate(eased, [0, 1], [action.fromScale ?? .92, 1], clamp)})`;
    } else if (action.type === 'draw' || action.type === 'trace') {
      opacity = Math.max(opacity, amount); strokeDasharray = 1; strokeDashoffset = 1 - amount;
      if (action.type === 'trace') {stroke = action.color ?? theme.accent; filter = amount > 0 && amount < 1 ? `drop-shadow(0 0 5px ${stroke})` : undefined;}
    } else if (action.type === 'move') {
      transform += ` translate(${interpolate(amount, [0, 1], [action.from.x, action.to.x], clamp)} ${interpolate(amount, [0, 1], [action.from.y, action.to.y], clamp)})`;
    } else if (action.type === 'highlight') {
      const pulse = Math.sin(amount * Math.PI);
      stroke = interpolateColors(pulse, [0, 1], [theme.line, action.color ?? theme.accent]);
      filter = `drop-shadow(0 0 ${Math.round(10 * pulse)}px ${action.color ?? theme.accent})`;
    } else {
      const from = {x: 0, y: 0, scale: 1, rotate: 0, ...action.from};
      const to = {...from, ...action.to};
      transform += ` translate(${interpolate(amount, [0, 1], [from.x, to.x], clamp)} ${interpolate(amount, [0, 1], [from.y, to.y], clamp)})`;
      transform += ` rotate(${interpolate(amount, [0, 1], [from.rotate, to.rotate], clamp)})`;
      transform += ` scale(${interpolate(amount, [0, 1], [from.scale, to.scale], clamp)})`;
    }
  }
  return {opacity, transform: transform.trim(), ...(strokeDasharray === undefined ? {} : {strokeDasharray}),
    ...(strokeDashoffset === undefined ? {} : {strokeDashoffset}), ...(stroke === undefined ? {} : {stroke}), ...(filter === undefined ? {} : {filter})};
}

