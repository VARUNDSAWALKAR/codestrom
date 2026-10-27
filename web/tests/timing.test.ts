import assert from 'node:assert/strict';
import {readFileSync, readdirSync} from 'node:fs';
import {test} from 'node:test';
import {activeBeat, activeCaption, activeScene, absoluteToRelative, beatState,
  relativeToAbsolute, relFrame, sceneBoundaries, sceneEndFrame} from '../src/lesson/timing';
import type {Beat, RenderProps} from '../src/lesson/types';
import {sampleProps} from '../src/remotion/sampleProps';

const samples = new URL('../../data/samples/', import.meta.url);
const fixtures = readdirSync(samples).filter((name) => name.endsWith('.props.json'));

test('Studio default props exactly match the original Python sample', () => {
  assert.deepEqual(sampleProps, JSON.parse(readFileSync(new URL('python_loop.props.json', samples), 'utf8')));
});

for (const name of fixtures) {
  // Trusted fixture boundary; structural/timing invariants are checked below.
  const props = JSON.parse(readFileSync(new URL(name, samples), 'utf8')) as RenderProps;
  const {lesson, timeline} = props;

  test(`${name}: every scene, beat, caption, and step has a valid position`, () => {
    assert.equal(timeline.audio, null);
    assert.equal(timeline.lesson_id, lesson.lesson_id);
    assert.equal(timeline.language, lesson.language);
    assert.equal(timeline.width, 1280);
    assert.equal(timeline.height, 720);
    assert.ok(timeline.fps > 0);
    assert.equal(timeline.scenes.length, lesson.scenes.length);
    const ids = new Set<string>();
    let end = 0;
    for (const [index, scene] of timeline.scenes.entries()) {
      assert.ok(!ids.has(scene.scene_id));
      ids.add(scene.scene_id);
      const content = lesson.scenes[index];
      assert.ok(content);
      assert.equal(scene.scene_id, content.id);
      assert.equal(scene.type, content.type);
      assert.equal(scene.start_frame, end);
      assert.ok(Number.isInteger(scene.duration_frames) && scene.duration_frames > 0);
      end = sceneEndFrame(scene);
      assert.equal(activeScene(timeline, scene.start_frame), scene);
      assert.equal(activeScene(timeline, end - 1), scene);
      assert.notEqual(activeScene(timeline, end), scene);
      let beatEnd = scene.start_frame;
      let introCount = 0;
      const steps = new Set<number>();
      for (const beat of scene.beats) {
        assert.ok(Number.isInteger(beat.start_frame) && Number.isInteger(beat.end_frame));
        assert.ok(beat.start_frame >= beatEnd);
        assert.ok(beat.end_frame > beat.start_frame && beat.end_frame <= end);
        beatEnd = beat.end_frame;
        assert.equal(activeBeat(scene.beats, beat.start_frame), beat);
        assert.notEqual(activeBeat(scene.beats, beat.end_frame), beat);
        assert.equal(relFrame(beat, scene), beat.start_frame - scene.start_frame);
        assert.equal(relativeToAbsolute(relFrame(beat, scene), scene), beat.start_frame);
        let narration: string;
        if (beat.step_index === null) {
          introCount++;
          assert.equal(beat.beat_id, `${scene.scene_id}.intro`);
          narration = content.narration;
        } else {
          assert.ok(Number.isInteger(beat.step_index) && beat.step_index >= 0);
          const step = content.steps[beat.step_index];
          assert.ok(step);
          assert.ok(!steps.has(beat.step_index));
          steps.add(beat.step_index);
          assert.equal(beat.beat_id, `${scene.scene_id}.step${beat.step_index}`);
          narration = step.narration;
          assert.equal(beatState(scene.beats, beat.step_index, beat.start_frame - 1), 'hidden');
          assert.equal(beatState(scene.beats, beat.step_index, beat.start_frame), 'active');
        }
        assert.ok(beat.captions.length > 0);
        assert.equal(beat.captions.map((caption) => caption.text).join(' '), narration);
        let captionEnd = beat.start_frame;
        for (const caption of beat.captions) {
          assert.ok(caption.text.trim());
          assert.ok(Number.isInteger(caption.start_frame) && Number.isInteger(caption.end_frame));
          assert.ok(caption.start_frame >= captionEnd);
          assert.ok(caption.end_frame > caption.start_frame && caption.end_frame <= beat.end_frame);
          assert.equal(activeCaption(timeline, caption.start_frame), caption);
          assert.equal(activeCaption(timeline, caption.end_frame - 1), caption);
          assert.notEqual(activeCaption(timeline, caption.end_frame), caption);
          captionEnd = caption.end_frame;
        }
      }
      assert.equal(introCount, content.narration === '' ? 0 : 1);
      assert.equal(steps.size, content.steps.length);
    }
    assert.equal(end, timeline.duration_frames);
    assert.deepEqual(sceneBoundaries(timeline), timeline.scenes.slice(1).map((scene) => scene.start_frame));
    assert.equal(activeScene(timeline, -1), undefined);
    assert.equal(activeCaption(timeline, timeline.duration_frames), undefined);
  });

  test(`${name}: visual activation and absolute/relative conversion hold on every frame`, () => {
    for (const scene of timeline.scenes) {
      for (let frame = scene.start_frame; frame < sceneEndFrame(scene); frame++) {
        assert.equal(relativeToAbsolute(absoluteToRelative(frame, scene), scene), frame);
        const latest = scene.beats.filter((beat) => beat.start_frame <= frame).at(-1);
        for (const beat of scene.beats) {
          if (beat.step_index === null) continue;
          const expected = frame < beat.start_frame ? 'hidden' : beat === latest ? 'active' : 'revealed';
          assert.equal(beatState(scene.beats, beat.step_index, frame), expected);
        }
        const caption = activeCaption(timeline, frame);
        if (caption) assert.ok(caption.start_frame <= frame && frame < caption.end_frame);
      }
    }
  });
}

test('visual step remains active in silence, becomes revealed at the next beat, and missing steps stay hidden', () => {
  const beats: Beat[] = [
    {beat_id: 's2.step0', step_index: 0, start_frame: 400, end_frame: 450, captions: []},
    {beat_id: 's2.step1', step_index: 1, start_frame: 460, end_frame: 510, captions: []},
  ];
  assert.equal(activeBeat(beats, 455), undefined);
  assert.equal(beatState(beats, 0, 455), 'active');
  assert.equal(beatState(beats, 0, 460), 'revealed');
  assert.equal(beatState(beats, 1, 460), 'active');
  assert.equal(beatState(beats, 99, 460), 'hidden');
});
