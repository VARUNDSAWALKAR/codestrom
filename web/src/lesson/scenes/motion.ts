import {interpolate, spring} from 'remotion';
import {beatState} from '../timing';
import type {TimelineScene} from '../types';

export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export const ramp = (frame: number, duration: number): number => interpolate(frame, [0, duration], [0, 1], clamp);
export const enter = (frame: number, fps: number): number => frame < 0 ? 0 :
  Math.min(1, Math.max(0, spring({frame, fps, config: {damping: 200}, durationInFrames: 12})));

export function stepMotion(scene: TimelineScene, index: number, absoluteFrame: number, fps: number) {
  const beat = scene.beats.find((item) => item.step_index === index);
  const state = beatState(scene.beats, index, absoluteFrame);
  const next = beat && scene.beats.find((item) => item.start_frame > beat.start_frame);
  const age = beat ? absoluteFrame - beat.start_frame : -1;
  const activation = !beat || age < 0 ? 0 : ramp(age, 8) *
    (next ? 1 - ramp(absoluteFrame - next.start_frame, 8) : 1);
  return {beat, state, age, activation, entrance: enter(age, fps)};
}
