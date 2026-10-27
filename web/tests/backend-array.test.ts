import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {arrayDemoFixture, arrayDemoProps} from '../src/fixtures/arrayFixtureData';
import type {VisualSpec, SpecializedSceneVisual} from '../src/types/visualSpec';
import {arrayBox, arrayObjectState, prepareArrayScene} from '../src/lesson/visual/backendArray';
import {relativeToAbsolute} from '../src/lesson/timing';

const prepare = () => prepareArrayScene(arrayDemoFixture.spec, arrayDemoProps, 's2');
function selected(spec: VisualSpec): SpecializedSceneVisual {
  const scene = spec.scenes[1]; assert.ok(scene && scene.fallback === null); return scene;
}

test('array slice consumes the unchanged real backend fixture, IDs and centered geometry', () => {
  const backend = JSON.parse(readFileSync(new URL('../../backend/tests/fixtures/visuals/array_grid_demo.json', import.meta.url), 'utf8'));
  assert.deepEqual(arrayDemoFixture, backend);
  const p = prepare();
  assert.deepEqual(p.objects.map((o) => o.id), ['cell0', 'cell1', 'cell2', 'cell3', 'cell4', 'interval']);
  assert.deepEqual([...p.labels.values()], ['1', '3', '5', '7', '9']);
  assert.deepEqual(p.objects, backend.spec.scenes[1].objects);
  assert.ok(Math.abs(arrayBox(p.objects[0]!).x - 138.88) < 1e-8);
  assert.equal(arrayBox(p.objects[0]!).y, 304);
  const region = arrayBox(p.objects[5]!), first = arrayBox(p.objects[3]!), last = arrayBox(p.objects[4]!);
  assert.ok(Math.abs(region.x - first.x) < 1e-8);
  assert.ok(Math.abs(region.x + region.width - last.x - last.width) < 1e-8);
});

test('reveal uses fractional measured beat boundaries and linear held opacity', () => {
  const p = prepare(), e = p.events.find((e) => e.action.id === 'a0')!, object = p.objects[0]!;
  const beat = p.timelineScene.beats.find((b) => b.beat_id === e.action.beat_id)!;
  assert.equal(e.start, beat.start_frame);
  assert.equal(e.end, beat.start_frame + .6 * (beat.end_frame - beat.start_frame));
  assert.equal(arrayObjectState(p, object, e.start - 1).opacity, 0);
  assert.ok(Math.abs(arrayObjectState(p, object, (e.start + e.end) / 2).opacity - .5) < 1e-12);
  assert.equal(arrayObjectState(p, object, e.end).opacity, 1);
  assert.equal(arrayObjectState(p, object, p.timelineScene.start_frame + p.timelineScene.duration_frames - 1).opacity, 1);
});

test('highlight holds its final style, other objects stay unchanged, backwards seeks are pure', () => {
  const p = prepare(), object = p.objects[2]!, e = p.events.find((e) => e.action.id === 'a1')!;
  const before = arrayObjectState(p, object, e.start - 1), middle = arrayObjectState(p, object, (e.start + e.end) / 2);
  const after = arrayObjectState(p, object, e.end);
  assert.notEqual(before.fill, middle.fill); assert.notEqual(after.fill, middle.fill);
  assert.deepEqual(after, arrayObjectState(p, object, e.end + 100));
  assert.deepEqual(before, arrayObjectState(p, object, e.start - 1));
  assert.equal(arrayObjectState(p, p.objects[1]!, e.end + 100).opacity, 1);
  assert.equal(arrayObjectState(p, p.objects[5]!, e.start).opacity, 0);
});

test('timeline scaling changes action duration, preserving phases and scene-relative conversion', () => {
  const p = prepare(), props = structuredClone(arrayDemoProps);
  props.timeline.duration_frames *= 3;
  for (const scene of props.timeline.scenes) {
    scene.start_frame *= 3; scene.duration_frames *= 3;
    for (const beat of scene.beats) {
      beat.start_frame *= 3; beat.end_frame *= 3;
      for (const cue of beat.captions) {cue.start_frame *= 3; cue.end_frame *= 3;}
    }
  }
  const other = prepareArrayScene(arrayDemoFixture.spec, props, 's2');
  assert.equal(other.events[0]!.end, 3 * p.events[0]!.end);
  const frame = (p.events[0]!.start + p.events[0]!.end) / 2;
  assert.ok(Math.abs(arrayObjectState(p, p.objects[0]!, frame).opacity - arrayObjectState(other, other.objects[0]!, frame * 3).opacity) < 1e-12);
  assert.equal(relativeToAbsolute(frame - p.timelineScene.start_frame, p.timelineScene), frame);
});

for (const mutation of ['version', 'extra', 'object', 'action', 'identity', 'beat', 'bounds', 'duplicate', 'overlap', 'discontinuity', 'group', 'semantics']) {
  test(`invalid/unsupported ${mutation} is rejected for whole-scene legacy fallback`, () => {
    const spec = structuredClone(arrayDemoFixture.spec), scene = selected(spec);
    if (mutation === 'version') Object.assign(spec, {visual_schema_version: 'visual-v2'});
    if (mutation === 'extra') Object.assign(spec, {untrusted: true});
    if (mutation === 'object') Object.assign(scene.objects[0]!, {kind: 'circle'});
    if (mutation === 'action') scene.actions[0] = {kind: 'move', id: 'a0', target: 'cell0', beat_id: 's2.step0', start: 0, end: .6, from_position: {x: .14, y: .5}, to_position: {x: .32, y: .5}};
    if (mutation === 'identity') spec.lesson_id = 'different-plan';
    if (mutation === 'beat') scene.actions[0]!.beat_id = 's3.step0';
    if (mutation === 'bounds') Object.assign(scene.objects[0]!, {position: {x: 0, y: .5}});
    if (mutation === 'duplicate') scene.objects.push(structuredClone(scene.objects[0]!));
    if (mutation === 'overlap') scene.actions.push({...scene.actions[0]!, id: 'a4'});
    if (mutation === 'discontinuity') scene.actions.push({...scene.actions[0]!, id: 'a4', beat_id: 's2.step1'});
    if (mutation === 'group') scene.objects.push({kind: 'group', id: 'group', role: 'Flat group', style: 'primary', label: null, children: ['cell0']});
    if (mutation === 'semantics') spec.provenance.semantics_version = 'unknown';
    assert.throws(() => prepareArrayScene(spec, arrayDemoProps, 's2'));
  });
}

test('successive compatible channels hold through gaps without future resets', () => {
  const spec = structuredClone(arrayDemoFixture.spec);
  selected(spec).actions.push({kind: 'reveal', id: 'a4', target: 'cell0', beat_id: 's2.step2', start: .2, end: .8, from_opacity: 1, to_opacity: .5});
  const p = prepareArrayScene(spec, arrayDemoProps, 's2'), first = p.events.find((e) => e.action.id === 'a0')!, next = p.events.find((e) => e.action.id === 'a4')!;
  assert.equal(arrayObjectState(p, p.objects[0]!, (first.end + next.start) / 2).opacity, 1);
  assert.equal(arrayObjectState(p, p.objects[0]!, next.end + 10).opacity, .5);
});

test('standalone text and source-bound labels are resolved as inert data', () => {
  const spec = structuredClone(arrayDemoFixture.spec);
  selected(spec).objects.push({kind: 'text', id: 'caption', role: 'Source label', style: 'primary',
    position: {x: .5, y: .8}, width: .4, height: .1, label: {kind: 'source', field: 'text', step_index: 1}});
  const p = prepareArrayScene(spec, arrayDemoProps, 's2');
  assert.equal(p.labels.get('caption'), 'Midpoint 5');
});

test('production Lesson and Remotion entry never hardcode the authored demonstration', () => {
  for (const name of ['src/lesson/Lesson.tsx', 'src/remotion/Root.tsx']) {
    const source = readFileSync(new URL(`../${name}`, import.meta.url), 'utf8');
    assert.ok(!source.includes('array-grid-demo') && !source.includes('ArrayDemo'));
  }
});
