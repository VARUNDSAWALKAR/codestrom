import assert from 'node:assert/strict';
import {test} from 'node:test';
import {loadMockVisualFixture, loadVisualFixture, visualFixtureNames} from '../src/fixtures';
import {parseVisualFixture, parseVisualSpec, parseVisualSpecJson} from '../src/utils/parseVisualSpec';

test('all requested VQ1 fixtures load against the exact visual-v1 contract', () => {
  assert.deepEqual(visualFixtureNames, ['binary-search', 'water-cycle', 'graph-traversal']);
  const layouts = visualFixtureNames.map((name) => loadVisualFixture(name).expected.layout);
  assert.deepEqual(layouts, ['code_walkthrough', 'spatial', 'graph_network']);
  for (const name of visualFixtureNames) {
    const fixture = loadVisualFixture(name);
    assert.equal(fixture.spec.lesson_id, fixture.source.lesson_id);
    assert.equal(fixture.spec.scenes.length, fixture.source.scenes.length);
  }
});

test('mock fixture loader builds contiguous absolute narration clocks and fractional action bindings', () => {
  for (const name of visualFixtureNames) {
    const fixture = loadMockVisualFixture(name); assert.equal(fixture.timeline.audio, null); assert.equal(fixture.mock, true);
    let end = 0;
    for (const scene of fixture.timeline.scenes) {
      assert.equal(scene.start_frame, end); end += scene.duration_frames;
      for (const beat of scene.beats) {
        assert.ok(beat.start_frame >= scene.start_frame && beat.end_frame <= end && beat.end_frame > beat.start_frame);
        assert.equal(beat.captions[0]?.text.length! > 0, true);
      }
    }
    assert.equal(end, fixture.timeline.duration_frames);
    for (const action of fixture.bound_actions) {
      const beat = fixture.timeline.scenes.flatMap((scene) => scene.beats).find((item) => item.beat_id === action.beat_id);
      assert.ok(beat && action.start_frame >= beat.start_frame && action.end_frame <= beat.end_frame);
    }
  }
});

test('fixture loads are isolated clones and validators reject unknown fields and broken references', () => {
  const first = loadVisualFixture('graph-traversal'); first.review_notes.push('mutation');
  assert.equal(loadVisualFixture('graph-traversal').review_notes.includes('mutation'), false);
  const fixture = loadVisualFixture('graph-traversal');
  assert.throws(() => parseVisualFixture({...fixture, injected: true}), /unknown field/);
  const spec = structuredClone(fixture.spec); const specialized = spec.scenes.find((scene) => scene.fallback === null)!;
  specialized.actions[0]!.target = 'missing'; assert.throws(() => parseVisualSpec(spec), /invalid object/);
  assert.throws(() => parseVisualSpecJson('{broken'), /not valid JSON/);
});

