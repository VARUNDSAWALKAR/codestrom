import type {Beat, Caption, Timeline, TimelineScene} from './types';

export type StepState = 'hidden' | 'active' | 'revealed';

/** All lookup frames are lesson-absolute, unless explicitly named relativeFrame. */
export const sceneEndFrame = (scene: TimelineScene): number =>
  scene.start_frame + scene.duration_frames;

export const sceneBoundaries = (timeline: Timeline): number[] =>
  timeline.scenes.slice(1).map((scene) => scene.start_frame);

export const activeScene = (timeline: Timeline, frame: number): TimelineScene | undefined =>
  timeline.scenes.find((scene) => frame >= scene.start_frame && frame < sceneEndFrame(scene));

/** Audio/caption beat: exclusive end, including the silent gaps between beats. */
export const activeBeat = (beats: readonly Beat[], frame: number): Beat | undefined =>
  beats.find((beat) => frame >= beat.start_frame && frame < beat.end_frame);

/** Visual activation persists across silence until the next beat starts. */
export function beatState(beats: readonly Beat[], stepIndex: number, frame: number): StepState {
  const beat = beats.find((item) => item.step_index === stepIndex);
  if (!beat || frame < beat.start_frame) return 'hidden';
  const next = beats.find((item) => item.start_frame > beat.start_frame);
  return next && frame >= next.start_frame ? 'revealed' : 'active';
}

export const absoluteToRelative = (frame: number, scene: TimelineScene): number =>
  frame - scene.start_frame;

export const relativeToAbsolute = (relativeFrame: number, scene: TimelineScene): number =>
  scene.start_frame + relativeFrame;

export const relFrame = (beat: Beat, scene: TimelineScene): number =>
  absoluteToRelative(beat.start_frame, scene);

export function activeCaption(timeline: Timeline, frame: number): Caption | undefined {
  const scene = activeScene(timeline, frame);
  const beat = scene && activeBeat(scene.beats, frame);
  return beat?.captions.find((caption) => frame >= caption.start_frame && frame < caption.end_frame);
}
