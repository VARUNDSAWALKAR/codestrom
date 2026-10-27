import assert from 'node:assert/strict';
import {test} from 'node:test';
import {diagramVisualSpec, flowLayout, gridLayout, interpretVisualSpec, networkLayout, parseRenderVisualSpec, resolveActions} from '../src/lesson/visual';
import {sampleProps} from '../src/remotion/sampleProps';

const scene = sampleProps.lesson.scenes.find((item) => item.type === 'diagram');
const timelineScene = sampleProps.timeline.scenes.find((item) => item.type === 'diagram');

test('Lesson v1 diagrams compile into deterministic VisualSpec primitives tied to timeline beats', () => {
  assert.ok(scene?.type === 'diagram' && timelineScene);
  const first = diagramVisualSpec(scene, timelineScene, sampleProps.lesson.language);
  assert.deepEqual(first, diagramVisualSpec(scene, timelineScene, sampleProps.lesson.language));
  assert.equal(parseRenderVisualSpec(first).primitives.length, first.primitives.length);
  const actionBeats = first.primitives.flatMap((primitive) => primitive.actions?.map((action) => action.beatId) ?? []);
  assert.ok(actionBeats.every((id) => timelineScene.beats.some((beat) => beat.beat_id === id)));
});

test('strict parser rejects executable-looking extras, duplicate ids, and malformed transforms', () => {
  assert.ok(scene?.type === 'diagram' && timelineScene);
  assert.throws(() => parseRenderVisualSpec({...diagramVisualSpec(scene, timelineScene, 'en'), eval: 'alert(1)'}), /unknown field/);
  const duplicate = diagramVisualSpec(scene, timelineScene, 'en'); duplicate.primitives.push(duplicate.primitives[0]!);
  assert.throws(() => parseRenderVisualSpec(duplicate), /Duplicate primitive id/);
  const malformed = diagramVisualSpec(scene, timelineScene, 'en');
  malformed.primitives[0]!.actions = [{type: 'transform', beatId: timelineScene.beats[0]!.beat_id, from: {}, to: {x: 2}}];
  assert.throws(() => parseRenderVisualSpec(malformed), /must contain a transform value/);
  const unknownBeat = diagramVisualSpec(scene, timelineScene, 'en');
  unknownBeat.primitives[0]!.actions = [{type: 'draw', beatId: 'missing.beat'}];
  assert.throws(() => interpretVisualSpec(unknownBeat, timelineScene), /unknown beat/);
});

test('animation progress is absolute-frame driven and reversible when scrubbing', () => {
  assert.ok(timelineScene); const beat = timelineScene.beats.find((item) => item.step_index !== null)!;
  const actions = [{type: 'reveal' as const, beatId: beat.beat_id, durationFrames: 10}];
  assert.equal(resolveActions(actions, timelineScene, beat.start_frame - 1, sampleProps.timeline.fps).opacity, 0);
  assert.equal(resolveActions(actions, timelineScene, beat.start_frame + 10, sampleProps.timeline.fps).opacity, 1);
  assert.equal(resolveActions(actions, timelineScene, beat.start_frame - 1, sampleProps.timeline.fps).opacity, 0);
});

test('educational layouts produce stable unique primitives for flow, grids, and networks', () => {
  const items = [{id: 'a', label: 'Input'}, {id: 'b', label: 'Process'}, {id: 'c', label: 'Output'}]; const beats = ['s.step0', 's.step1', 's.step2'];
  for (const primitives of [flowLayout(items, beats), gridLayout(items, 2, beats), networkLayout(items, [{from: 'a', to: 'b'}, {from: 'b', to: 'c'}], beats)]) {
    assert.equal(new Set(primitives.map((primitive) => primitive.id)).size, primitives.length);
    assert.deepEqual(primitives, structuredClone(primitives));
  }
});

