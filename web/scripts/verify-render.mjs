import assert from 'node:assert/strict';
import {mkdir, readFile, readdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderStill, selectComposition} from '@remotion/renderer';

const artifacts = new URL('../.validation/', import.meta.url);
await mkdir(artifacts, {recursive: true});
const serveUrl = await bundle({entryPoint: fileURLToPath(new URL('../src/remotion/index.ts', import.meta.url)),
  outDir: fileURLToPath(new URL('bundle/', artifacts))});
const browser = await openBrowser('chrome', {browserExecutable: process.env.CHROMIUM_PATH ?? '/usr/bin/chromium'});
try {
  const samples = new URL('../../data/samples/', import.meta.url);
  for (const name of (await readdir(samples)).filter((name) => name.endsWith('.props.json'))) {
    const inputProps = JSON.parse(await readFile(new URL(name, samples), 'utf8'));
    const composition = await selectComposition({serveUrl, id: 'Lesson', inputProps, puppeteerInstance: browser});
    assert.equal(composition.fps, inputProps.timeline.fps);
    assert.equal(composition.durationInFrames, inputProps.timeline.duration_frames);
    assert.equal(composition.width, 1280);
    assert.equal(composition.height, 720);
    for (const scene of inputProps.timeline.scenes) {
      const beat = scene.beats.find((item) => item.step_index !== null) ?? scene.beats[0];
      assert.ok(beat);
      await renderStill({serveUrl, composition, inputProps, puppeteerInstance: browser,
        frame: Math.min(beat.start_frame + 15, beat.end_frame - 1),
        output: fileURLToPath(new URL(`render-${name}-${scene.scene_id}.png`, artifacts))});
    }
    const first = inputProps.timeline.scenes[0];
    const firstBeat = first.beats.find((item) => item.step_index !== null) ?? first.beats[0];
    const repeat = new URL(`repeat-${name}.png`, artifacts);
    await renderStill({serveUrl, composition, inputProps, puppeteerInstance: browser,
      frame: Math.min(firstBeat.start_frame + 15, firstBeat.end_frame - 1), output: fileURLToPath(repeat)});
    assert.deepEqual(await readFile(repeat), await readFile(new URL(`render-${name}-${first.scene_id}.png`, artifacts)), 'Same frame and props must render identically after out-of-order scenes');
    console.log(`${name}: metadata ${composition.fps} fps / ${composition.durationInFrames} frames; all ${inputProps.timeline.scenes.length} scenes rendered`);
  }
} finally {
  await browser.close({silent: true});
}
