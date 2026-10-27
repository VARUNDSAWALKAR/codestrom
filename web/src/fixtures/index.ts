import binarySearchJson from './data/binary-search.visual.json';
import graphTraversalJson from './data/graph-traversal.visual.json';
import waterCycleJson from './data/water-cycle.visual.json';
import {bindVisualActions, parseVisualFixture} from '../utils/parseVisualSpec';
import type {MockVisualFixture, NarrationBeat, VisualFixture, VisualTimeline} from '../types/visualSpec';

export type VisualFixtureName = 'binary-search' | 'water-cycle' | 'graph-traversal';
const rawFixtures: Record<VisualFixtureName, unknown> = {
  'binary-search': binarySearchJson,
  'water-cycle': waterCycleJson,
  'graph-traversal': graphTraversalJson,
};

const validated = new Map<VisualFixtureName, VisualFixture>();
export const visualFixtureNames = Object.freeze(Object.keys(rawFixtures) as VisualFixtureName[]);

/** Loads a validated clone so tests and stories cannot mutate the shared fixture cache. */
export function loadVisualFixture(name: VisualFixtureName): VisualFixture {
  let fixture = validated.get(name);
  if (!fixture) {fixture = parseVisualFixture(rawFixtures[name]); validated.set(name, fixture);}
  return structuredClone(fixture);
}

function mockFrames(text: string, fps: number): number {
  const words = text.trim().split(/\s+/u).filter(Boolean).length;
  return Math.max(fps, Math.round(words * fps * .34));
}

/** Creates a silent, deterministic development clock; production must use the measured backend timeline. */
export function createMockTimeline(fixture: VisualFixture): VisualTimeline {
  const fps = 30 as const; let cursor = 0;
  const scenes = fixture.source.scenes.map((scene) => {
    const start_frame = cursor; const narration = [
      ...(scene.narration.trim() ? [{beat_id: `${scene.id}.intro`, step_index: null, text: scene.narration}] : []),
      ...scene.steps.map((step, step_index) => ({beat_id: `${scene.id}.step${step_index}`, step_index, text: step.narration})),
    ];
    const beats: NarrationBeat[] = narration.map((entry) => {
      const start = cursor; const end = start + mockFrames(entry.text, fps); cursor = end + Math.round(fps * .12);
      return {beat_id: entry.beat_id, step_index: entry.step_index, start_frame: start, end_frame: end,
        captions: [{text: entry.text, start_frame: start, end_frame: end}]};
    });
    const duration_frames = Math.max(fps, cursor - start_frame); cursor = start_frame + duration_frames;
    return {scene_id: scene.id, type: scene.type, start_frame, duration_frames, beats};
  });
  return {timeline_version: 1, lesson_id: fixture.source.lesson_id, language: fixture.source.language,
    variant: `${fixture.source.language}-mock`, fps, width: 1280, height: 720, duration_frames: cursor,
    audio: null, voice: {engine: 'mock', voice_id: 'silent-fixture', speed: 1}, tempo: 1, scenes};
}

export function loadMockVisualFixture(name: VisualFixtureName): MockVisualFixture {
  const fixture = loadVisualFixture(name); const timeline = createMockTimeline(fixture);
  return {...fixture, timeline, bound_actions: bindVisualActions(fixture.spec, timeline), mock: true};
}

