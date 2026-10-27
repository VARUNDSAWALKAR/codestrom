import assert from 'node:assert/strict';
import {readFile, mkdir} from 'node:fs/promises';
import {chromium} from 'playwright-core';

const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH ?? '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
const page = await browser.newPage({viewport: {width: 1280, height: 720}});
const samples = new URL('../../data/samples/', import.meta.url);
const artifacts = new URL('../.validation/', import.meta.url); await mkdir(artifacts, {recursive: true});
const python = JSON.parse(await readFile(new URL('python_loop.props.json', samples), 'utf8'));
async function show(props, frame) {
  await page.evaluate((input) => window.lessonTest.mount(input), props);
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await page.evaluate((value) => window.lessonTest.seek(value), frame);
  await page.evaluate(async () => {await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))); await document.fonts.ready;});
}
try {
  await page.goto('http://127.0.0.1:5173/tests/browser.html'); await page.waitForFunction(() => window.lessonTest);
  // Assert rendered highlights/output after out-of-order seeking, not just helper values.
  await show(python, 800);
  assert.equal(await page.locator('[data-code-output="lines"]').textContent(), '0\n1');
  await show(python, 882);
  assert.equal(await page.locator('[data-code-output="lines"]').textContent(), '0\n1\n2');
  await show(python, 400); assert.equal(await page.locator('[data-code-highlight]').count(), 0);
  await show(python, 430); assert.equal(await page.locator('[data-code-highlight]').getAttribute('data-code-highlight'), '1');
  assert.equal(await page.locator('[data-code-output="lines"]').textContent(), '');
  await show(python, 710); assert.equal(await page.locator('[data-code-highlight]').getAttribute('data-code-highlight'), '2');
  for (const name of ['python_loop', 'newtons_second_law', 'water_cycle']) {
    const props = JSON.parse(await readFile(new URL(`${name}.props.json`, samples), 'utf8'));
    for (const timed of props.timeline.scenes.filter((scene) => scene.type === 'diagram')) {
      for (const [stage, frame] of [['begin', timed.start_frame], ['middle', timed.start_frame + Math.floor(timed.duration_frames / 2)], ['end', timed.start_frame + timed.duration_frames - 1]]) {
        await show(props, frame);
        await page.screenshot({path: new URL(`diagram-${name}-${timed.scene_id}-${stage}.png`, artifacts).pathname});
        const boxes = await page.locator('[data-diagram-box]').evaluateAll((elements) => elements.map((element) => {
          const rect = element.getBoundingClientRect(); return {x: rect.x, right: rect.right, y: rect.y, bottom: rect.bottom};
        }));
        for (const box of boxes) assert.ok(box.x >= 63 && box.right <= 1217 && box.y >= 119 && box.bottom <= 581);
      }
    }
  }
  // Geometry edge cases use explicit mock fixture beats, never fabricated audio.
  for (const layout of ['flow', 'cycle', 'labelled']) for (let count = 2; count <= 6; count++) {
    const props = structuredClone(python);
    const scene = props.lesson.scenes[2]; const timed = props.timeline.scenes[2];
    scene.layout = layout; if (layout !== 'flow') scene.center = 'Concept';
    scene.narration = ''; scene.steps = Array.from({length: count}, (_, index) => ({text: `Step ${index + 1}`, note: 'A short note', narration: 'Mock beat.'}));
    const interval = Math.floor(timed.duration_frames / count);
    timed.beats = scene.steps.map((_, index) => ({beat_id: `${scene.id}.step${index}`, step_index: index,
      start_frame: timed.start_frame + index * interval, end_frame: timed.start_frame + (index + 1) * interval, captions: []}));
    await show(props, timed.start_frame + timed.duration_frames - 1);
    assert.equal(await page.locator('[data-diagram-box]').count(), count);
    const boxes = await page.locator('[data-diagram-box]').evaluateAll((elements) => elements.map((element) => {
      const rect = element.getBoundingClientRect(); return {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom};
    }));
    for (const [index, box] of boxes.entries()) {
      assert.ok(box.left >= 63 && box.right <= 1217 && box.top >= 119 && box.bottom <= 581);
      for (const other of boxes.slice(index + 1)) assert.ok(box.right <= other.left || box.left >= other.right || box.bottom <= other.top || box.top >= other.bottom);
    }
    if (layout === 'cycle') assert.equal(await page.locator(`[data-connector-from="${count - 1}"][data-connector-to="0"]`).count(), 1);
    if (count === 6) await page.screenshot({path: new URL(`diagram-${layout}-6.png`, artifacts).pathname});
  }
  for (const topic of ['python_loop', 'newtons_second_law', 'water_cycle']) for (const [language, heading, text] of [
    ['hi', 'Python में एक लूप कैसे काम करता है और कब रुकता है?', 'हर मान के लिए दोहराएँ'],
    ['kn', 'Python ಲೂಪ್ ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ ಮತ್ತು ಯಾವಾಗ ನಿಲ್ಲುತ್ತದೆ?', 'ಪ್ರತಿ ಮೌಲ್ಯಕ್ಕೂ ಪುನರಾವರ್ತಿಸಿ'],
  ]) {
    const props = JSON.parse(await readFile(new URL(`${topic}.props.json`, samples), 'utf8')); props.lesson.language = language; props.timeline.language = language;
    props.lesson.scenes[0].heading = heading;
    for (const scene of props.lesson.scenes.slice(1)) {scene.heading = heading; for (const step of scene.steps) {if (scene.type !== 'formula') step.text = text; if (scene.type === 'diagram' || scene.type === 'formula') step.note = text;}}
    for (const timed of props.timeline.scenes) for (const beat of timed.beats) for (const caption of beat.captions) caption.text = `${text} · range(3) · 0, 1, 2`;
    for (const timed of props.timeline.scenes) {
      const originalCode = props.lesson.scenes.find((scene) => scene.type === 'code_walkthrough')?.code;
      await show(props, timed.start_frame + timed.duration_frames - 20);
      const clipped = await page.locator('[data-scene-id] div[lang]').evaluateAll((elements) => elements.filter((element) => element.scrollHeight > element.clientHeight + 2 || element.scrollWidth > element.clientWidth + 2).map((element) => element.textContent));
      assert.deepEqual(clipped, [], `${language}/${timed.type}: text must fit`);
      if (timed.type === 'code_walkthrough') assert.equal(await page.locator('[data-code-line] code').allTextContents().then((lines) => lines.join('\n')), originalCode);
      await page.screenshot({path: new URL(`multilingual-${topic}-${language}-${timed.type}.png`, artifacts).pathname});
    }
  }
  const chromiumSession = await page.context().newCDPSession(page);
  await chromiumSession.send('Emulation.setCPUThrottlingRate', {rate: 4});
  await show(python, 430); await page.evaluate(() => window.lessonTest.seek(710));
  await page.waitForFunction(() => document.querySelector('[data-code-highlight]')?.getAttribute('data-code-highlight') === '2');
  console.log('PASS: backward scrubbing; rendered highlights/output; all diagram start/middle/end frames; 2–6 nodes in all layouts; long Hindi/Kannada text; code preservation; 4× CPU-throttled frame update.');
} finally {await browser.close();}
