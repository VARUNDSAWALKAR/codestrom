import assert from 'node:assert/strict';
import {mkdir, readFile, readdir} from 'node:fs/promises';
import {chromium} from 'playwright-core';

// Run npm run dev and npm run studio first. Uses the installed local browser.
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH ?? '/usr/bin/chromium',
  headless: true, args: ['--no-sandbox']});
const page = await browser.newPage({viewport: {width: 1280, height: 800}});
const errors = [];
const externalRequests = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('request', (request) => {
  const url = new URL(request.url());
  if (['http:', 'https:'].includes(url.protocol) && !['localhost', '127.0.0.1'].includes(url.hostname)) {
    externalRequests.push(request.url());
  }
});
const artifacts = new URL('../.validation/', import.meta.url);
await mkdir(artifacts, {recursive: true});
let frameChecks = 0;
try {
  await page.goto('http://127.0.0.1:5173/tests/browser.html');
  await page.waitForFunction(() => Boolean(window.lessonTest));
  const samples = new URL('../../data/samples/', import.meta.url);
  const names = (await readdir(samples)).filter((name) => name.endsWith('.props.json'));
  for (const name of names) {
    const props = JSON.parse(await readFile(new URL(name, samples), 'utf8'));
    await page.evaluate((input) => window.lessonTest.mount(input), props);
    await page.locator('[data-scene-id]').waitFor();
    for (const scene of props.timeline.scenes) {
      const frames = new Set([scene.start_frame + 15,
        ...scene.beats.map((beat) => Math.min(beat.start_frame + 12, beat.end_frame - 1)),
        scene.start_frame + scene.duration_frames - 1]);
      for (const frame of frames) {
        await page.evaluate((value) => window.lessonTest.seek(value), frame);
        await page.waitForFunction((id) => document.querySelector('[data-scene-id]')?.getAttribute('data-scene-id') === id, scene.scene_id);
        // Flush React's frame update and font layout before reading geometry.
        await page.evaluate(async () => {
          await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
          await document.fonts.ready;
        });
        const activeBeat = scene.beats.find((beat) => frame >= beat.start_frame && frame < beat.end_frame);
        const caption = activeBeat?.captions.find((cue) => frame >= cue.start_frame && frame < cue.end_frame);
        const captionElement = page.locator('[data-chrome="caption"]');
        const actualCaption = await captionElement.count() ? await captionElement.textContent() : null;
        assert.equal(actualCaption, caption?.text ?? null, `${name}/${scene.scene_id}/${frame}: caption`);
        assert.equal(await page.locator('[data-chrome="heading"]').count(), scene.type === 'title_card' ? 0 : 1);
        // Player seeds its shared audio-tag pool with an internal silent data URI.
        assert.deepEqual(await page.locator('audio').evaluateAll((elements) =>
          elements.filter((element) => !element.paused ||
            (element.currentSrc && !element.currentSrc.startsWith('data:audio/')))
            .map((element) => element.currentSrc)), [], 'Mock timeline must have no narration source or active audio');
        const content = props.lesson.scenes.find((item) => item.id === scene.scene_id);
        if (scene.type === 'title_card') {
          assert.ok((await page.locator('[data-title="content"]').textContent()).includes(content.heading));
        } else if (scene.type === 'code_walkthrough') {
          const latest = scene.beats.filter((beat) => beat.step_index !== null && beat.start_frame <= frame).at(-1);
          const step = latest ? content.steps[latest.step_index] : undefined;
          assert.equal(await page.locator('[data-code="state"]').textContent(), 'State' + (step?.text ?? ''));
          assert.equal(await page.locator('[data-code-line]').count(), content.code.split('\n').length);
          if (!latest) assert.equal(await page.locator('[data-code-highlight]').count(), 0);
        } else {
          const attribute = scene.type === 'diagram' ? 'data-diagram-step' : scene.type === 'formula' ? 'data-formula-step' : 'data-recap-step';
          const revealed = scene.beats.filter((beat) => beat.step_index !== null && beat.start_frame <= frame);
          assert.equal(await page.locator(`[${attribute}]`).count(), revealed.length);
        }
        const boxes = await page.evaluate(() => {
          const box = (selector) => {
            const element = document.querySelector(selector);
            if (!element) return null;
            const rect = element.getBoundingClientRect();
            return {x: rect.x, y: rect.y, right: rect.right, bottom: rect.bottom};
          };
          return {scene: box('[data-scene-id]'), heading: box('header'),
            caption: box('[data-chrome="caption"]'), progress: box('[data-chrome="progress"]')};
        });
        assert.deepEqual(boxes.scene, {x: 0, y: 0, right: 1280, bottom: 720});
        if (boxes.caption) assert.deepEqual(boxes.caption, {x: 64, y: 604, right: 1216, bottom: 692});
        if (boxes.heading) assert.ok(boxes.heading.y >= 0 && boxes.heading.bottom <= 96);
        assert.deepEqual(boxes.progress, {x: 0, y: 714, right: 1280, bottom: 720});
        frameChecks++;
      }
      await page.screenshot({path: new URL(`${name}-${scene.scene_id}.png`, artifacts).pathname});
    }
    console.log(`${name}: scene positions, captions, steps, silence, and progress verified`);
  }
  // Exercise the requested Indic fonts with script text; these are font probes,
  // not claims that real translated backend samples or audio exist.
  const base = JSON.parse(await readFile(new URL('python_loop.props.json', samples), 'utf8'));
  for (const [language, text, family] of [
    ['hi', 'एक लूप हर मान के लिए दोहराता है।', 'Noto Sans Devanagari'],
    ['kn', 'ಪ್ರತಿ ಮೌಲ್ಯಕ್ಕೂ ಲೂಪ್ ಪುನರಾವರ್ತಿಸುತ್ತದೆ.', 'Noto Sans Kannada'],
  ]) {
    const input = structuredClone(base);
    input.lesson.language = language;
    input.timeline.language = language;
    input.lesson.scenes[0].heading = text;
    input.timeline.scenes[0].beats[0].captions[0].text = text;
    await page.evaluate((props) => window.lessonTest.mount(props), input);
    await page.evaluate(() => window.lessonTest.seek(30));
    await page.waitForFunction((font) => [...document.fonts].some((item) => item.family === font && item.status === 'loaded'), family);
    await page.evaluate(() => document.fonts.ready);
    assert.equal(await page.locator('[data-scene-id]').getAttribute('lang'), language);
    assert.ok((await page.locator('[data-scene-id]').evaluate((element) => getComputedStyle(element).fontFamily)).includes(family));
    await page.screenshot({path: new URL(`fonts-${language}.png`, artifacts).pathname});
  }
  await page.evaluate((props) => window.lessonTest.mount({...props, showCaptions: false}), base);
  await page.evaluate(() => window.lessonTest.seek(30));
  await page.waitForFunction(() => !document.querySelector('[data-chrome="caption"]'));
  assert.deepEqual(errors, []);
  assert.deepEqual(externalRequests, [], 'Lesson application must not request external services');
  // Studio's development UI probes Remotion's bug/update service. Block all
  // nonlocal requests for the Studio check; composition playback needs none.
  await page.route('**/*', async (route) => {
    const host = new URL(route.request().url()).hostname;
    if (host && !['localhost', '127.0.0.1'].includes(host)) return route.abort();
    return route.continue();
  });
  await page.goto('http://127.0.0.1:3000/Lesson');
  await page.locator('[data-scene-id="s1"]').waitFor();
  assert.ok((await page.content()).includes('Lesson'));
  assert.deepEqual(errors, []);
  console.log(`PASS: ${frameChecks} sample frame checks; Hindi/Kannada fonts; captions toggle; no external lesson requests; Studio composition with external requests blocked.`);
} finally {
  await browser.close();
}
