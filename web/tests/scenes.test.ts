import assert from 'node:assert/strict';
import {test} from 'node:test';
import {codeState, lineRuns, tokenize} from '../src/lesson/scenes/code';
import {diagramGeometry} from '../src/lesson/scenes/geometry';
import {formulaSegments} from '../src/lesson/scenes/Formula';
import {parseRenderProps} from '../src/lesson/validate';
import {sampleProps} from '../src/remotion/sampleProps';
import type {CodeLanguage, FormulaScene} from '../src/lesson/types';
import {timelineSrt} from '../src/app/captions';

test('code highlighting, output reveal, and backward scrubbing derive only from absolute beats', () => {
  const scene = sampleProps.lesson.scenes.find((item) => item.type === 'code_walkthrough');
  const timeline = sampleProps.timeline.scenes.find((item) => item.type === 'code_walkthrough');
  assert.ok(scene?.type === 'code_walkthrough' && timeline);
  assert.deepEqual(codeState(scene, timeline, timeline.start_frame).runs, []);
  for (const beat of [...timeline.beats].reverse()) {
    if (beat.step_index === null) continue;
    assert.deepEqual(codeState(scene, timeline, beat.start_frame).runs, lineRuns(scene.steps[beat.step_index]?.lines ?? []));
  }
  const outputBeat = timeline.beats.find((beat) => beat.step_index === 2);
  assert.ok(outputBeat);
  assert.deepEqual(codeState(scene, timeline, outputBeat.start_frame - 1).output, []);
  assert.deepEqual(codeState(scene, timeline, outputBeat.start_frame).output, ['0']);
  assert.deepEqual(codeState(scene, timeline, outputBeat.start_frame + 64).output, ['0', '1']);
  assert.deepEqual(codeState(scene, timeline, outputBeat.end_frame - 1).output, ['0', '1', '2']);
  assert.deepEqual(codeState(scene, timeline, outputBeat.end_frame + 3).output, ['0', '1', '2']);
  assert.deepEqual(codeState(scene, timeline, outputBeat.start_frame - 1).output, []);
  const multi = structuredClone(scene);
  multi.steps[0]!.output = 'earlier';
  assert.deepEqual(codeState(multi, timeline, outputBeat.end_frame).output, ['earlier', '0', '1', '2']);
});
test('line ranges are deduplicated and nonconsecutive highlights stay separate', () => {
  assert.deepEqual(lineRuns([3, 1, 2, 2, 7, 9, 10]), [{start: 1, count: 3}, {start: 7, count: 1}, {start: 9, count: 2}]);
});
test('Binary Search multi-line steps preserve the schema’s one-based line indexing', () => {
  assert.deepEqual(lineRuns([5, 6, 8, 9]), [{start: 5, count: 2}, {start: 8, count: 2}]);
  assert.deepEqual(lineRuns([1, 3, 4]), [{start: 1, count: 1}, {start: 3, count: 2}]);
});
test('every supported language is tokenized as inert text, preserving whitespace and HTML-like input', () => {
  const code = '    print("<script>never run</script>", 3) // comment';
  for (const language of ['python', 'javascript', 'java', 'c', 'cpp', 'other'] as CodeLanguage[]) {
    assert.equal(tokenize(code, language).map((token) => token.text).join(''), code);
  }
});
for (const layout of ['flow', 'cycle', 'labelled'] as const) for (let n = 2; n <= 6; n++) {
  test(`${layout}/${n}: deterministic geometry fits the frame with nonoverlapping boxes`, () => {
    const geometry = diagramGeometry(layout, n);
    assert.deepEqual(geometry, diagramGeometry(layout, n));
    assert.equal(geometry.boxes.length, n);
    for (const [index, box] of geometry.boxes.entries()) {
      assert.ok(box.x - box.width / 2 >= 64 && box.x + box.width / 2 <= 1216);
      assert.ok(box.y - box.height / 2 >= 120 && box.y + box.height / 2 <= 580);
      for (const other of geometry.boxes.slice(index + 1)) {
        assert.ok(Math.abs(box.x - other.x) >= (box.width + other.width) / 2 ||
          Math.abs(box.y - other.y) >= (box.height + other.height) / 2);
      }
    }
    if (layout === 'cycle') assert.ok(geometry.connectors.some((connector) => connector.to === 0 && connector.reveal === n - 1));
    if (layout === 'flow' && n > 4) assert.ok(geometry.connectors[2]?.path.includes('V 340'));
  });
}
test('formula segmentation preserves the expression and excludes unmatched and explicitly excluded parts', () => {
  const scene: FormulaScene = {id: 'f', type: 'formula', heading: 'Force', narration: '', expression: 'F = m × a', steps: [
    {text: 'F', note: 'Force', narration: 'Force.'}, {text: 'm', note: 'Mass', narration: 'Mass.'},
    {text: 'unknown', note: 'Extra', narration: 'Extra.'}, {text: 'a', note: 'Acceleration', narration: 'Acceleration.', in_expression: false}]};
  const segments = formulaSegments(scene);
  assert.equal(segments.map((segment) => segment.text).join(''), scene.expression);
  assert.deepEqual(segments.filter((segment) => segment.index !== null).map((segment) => segment.index), [0, 1]);
});
test('render boundary rejects missing media, malformed timing, remote assets, and invalid highlights', () => {
  assert.equal(parseRenderProps(sampleProps), sampleProps);
  for (const change of [
    (props: typeof sampleProps) => {props.timeline.scenes[1]!.start_frame++;},
    (props: typeof sampleProps) => {props.timeline.scenes[0]!.beats[0]!.captions[0]!.end_frame = 999999;},
    (props: typeof sampleProps) => {props.timeline.audio = {web: 'https://example.com/a.m4a', wav: '/media/a.wav'};},
  ]) {
    const props = structuredClone(sampleProps); change(props); assert.throws(() => parseRenderProps(props));
  }
});
test('SRT keeps Unicode text and uses absolute frames at the actual timeline fps', () => {
  const props = structuredClone(sampleProps);
  props.timeline.scenes[0]!.beats[0]!.captions[0]!.text = 'लूप · ಲೂಪ್ · range(3)';
  const srt = timelineSrt(props.timeline);
  assert.ok(srt.startsWith('1\n00:00:00,300 --> 00:00:05,600\nलूप · ಲೂಪ್ · range(3)'));
  assert.ok(srt.includes('00:01:03,733 --> 00:01:07,200'));
});
