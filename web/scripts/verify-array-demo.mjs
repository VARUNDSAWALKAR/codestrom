// Local-only authored-fixture QA. No inference, audio generation or full export.
import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile, access} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash, randomUUID} from 'node:crypto';
import {tmpdir} from 'node:os';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderStill, renderMedia, selectComposition} from '@remotion/renderer';
import {createServer} from 'vite';
import {chromium} from 'playwright-core';
import {arrayDemoFixture, arrayDemoProps} from '../src/fixtures/arrayFixtureData.ts';
import {prepareArrayScene, arrayObjectState} from '../src/lesson/visual/backendArray.ts';

const web = fileURLToPath(new URL('../', import.meta.url));
const out = path.resolve(process.argv[2] ?? path.join(tmpdir(), `blu-array-qa-${randomUUID()}`));
await mkdir(out, {recursive: true});
const executable = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
await access(executable); // Never download a browser.
const prepared = prepareArrayScene(arrayDemoFixture.spec, arrayDemoProps, 's2');
const frames = [...new Set(prepared.events.flatMap((e) => [Math.floor(e.start) - 1, Math.floor((e.start + e.end) / 2), Math.ceil(e.end) + 1]))];
const report = {fixture: 'backend/tests/fixtures/visuals/array_grid_demo.json',
  clock: 'existing createMockTimeline: silent authored-fixture development clock, not measured speech',
  frames, events: prepared.events, stills: [], browser: [], fallback: {}, errors: []};
const save = () => writeFile(path.join(out, 'verification.json'), JSON.stringify(report, null, 2));
await writeFile(path.join(out, 'timeline.json'), JSON.stringify(arrayDemoProps.timeline, null, 2));
let renderer, server, browser;
try {
  const serveUrl = await bundle({entryPoint: path.join(web, 'src/remotion/array-demo.tsx'), rootDir: web,
    publicDir: path.join(web, 'public'), outDir: path.join(out, 'bundle'), enableCaching: false});
  renderer = await openBrowser('chrome', {browserExecutable: executable});
  const composition = await selectComposition({serveUrl, id: 'BackendArrayDemo', inputProps: {invalid: false}, puppeteerInstance: renderer});
  for (const frame of [...frames, frames[4]]) {
    const output = path.join(out, `frame-${frame}${report.stills.some((s) => s.frame === frame) ? '-repeat' : ''}.png`);
    await renderStill({serveUrl, composition, inputProps: {invalid: false}, frame, output, puppeteerInstance: renderer});
    report.stills.push({frame, file: path.basename(output), sha256: createHash('sha256').update(await readFile(output)).digest('hex')});
  }
  assert.equal(report.stills.at(-1).sha256, report.stills.find((s) => s.frame === frames[4]).sha256);
  report.deterministic_repeat = true;
  const invalidComposition = await selectComposition({serveUrl, id: 'BackendArrayDemo', inputProps: {invalid: true}, puppeteerInstance: renderer});
  assert.equal(invalidComposition.props.invalid, true);
  await renderStill({serveUrl, composition: invalidComposition, inputProps: {invalid: true}, frame: frames[5],
    output: path.join(out, 'fallback.png'), puppeteerInstance: renderer});
  report.fallback.remotion = 'rendered trusted legacy diagram with rejected version';
  // A short silent QA clip spanning midpoint emphasis and interval reveal.
  const range = [frames[3], frames[8]];
  await renderMedia({serveUrl, composition, inputProps: {invalid: false}, puppeteerInstance: renderer,
    outputLocation: path.join(out, 'array-demo.mp4'), frameRange: range,
    codec: 'h264', pixelFormat: 'yuv420p', crf: 23, muted: true, concurrency: 2});
  report.clip = {file: 'array-demo.mp4', frameRange: range, silent: true};
  await save();
  server = await createServer({root: web, server: {host: '127.0.0.1', port: 5173, strictPort: true}});
  await server.listen();
  browser = await chromium.launch({executablePath: executable, headless: true});
  const page = await browser.newPage({viewport: {width: 1280, height: 720}, deviceScaleFactor: 1});
  page.on('pageerror', (error) => report.errors.push(error.message));
  await page.route('**/*', (route) => {
    const url = new URL(route.request().url());
    if (['http:', 'https:'].includes(url.protocol) && !['127.0.0.1', 'localhost'].includes(url.hostname)) {
      report.errors.push(`External request blocked: ${url.href}`); return route.abort();
    }
    return route.continue();
  });
  await page.goto('http://127.0.0.1:5173/tests/array-demo.html');
  await page.waitForFunction(() => Boolean(window.arrayDemo));
  for (const frame of frames) {
    await page.evaluate((f) => window.arrayDemo.seek(f), frame);
    await page.locator('[data-backend-visual="s2"]').waitFor();
    await page.evaluate(async () => {await document.fonts.ready; await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));});
    const actual = await page.locator('[data-backend-object]').evaluateAll((elements) => elements.map((e) => ({
      id: e.getAttribute('data-backend-object'), opacity: Number(e.getAttribute('opacity')),
      fill: e.querySelector('rect')?.getAttribute('fill'), stroke: e.querySelector('rect')?.getAttribute('stroke'), label: e.querySelector('text')?.textContent,
      paintedFill: e.querySelector('rect') ? getComputedStyle(e.querySelector('rect')).fill : null,
      paintedStroke: e.querySelector('rect') ? getComputedStyle(e.querySelector('rect')).stroke : null,
    })));
    assert.deepEqual(actual.map((o) => o.id), prepared.objects.map((o) => o.id));
    for (const object of prepared.objects) {
      const state = arrayObjectState(prepared, object, frame), rendered = actual.find((o) => o.id === object.id);
      assert.ok(Math.abs(rendered.opacity - state.opacity) < 1e-8);
      assert.equal(rendered.stroke, state.stroke);
      assert.equal(rendered.fill, object.kind === 'highlight_region' ? 'none' : state.fill);
    }
    assert.deepEqual(actual.slice(0, 5).map((o) => o.label), ['1', '3', '5', '7', '9']);
    const screenshot = `browser-${frame}.png`;
    await page.screenshot({path: path.join(out, screenshot)});
    report.browser.push({frame, file: screenshot, objects: actual});
  }
  await page.evaluate(() => window.arrayDemo.mount(true));
  await page.evaluate((f) => window.arrayDemo.seek(f), frames[5]);
  await page.locator('[data-backend-fallback]').waitFor();
  assert.equal(await page.locator('[data-backend-visual]').count(), 0);
  assert.ok((await page.locator('[data-visual-spec]').count()) > 0);
  assert.ok((await page.locator('svg text').allTextContents()).some((s) => s.includes('Midpoint 5')));
  report.fallback.browser = 'invalid version visibly routed to trusted legacy diagram';
  await page.screenshot({path: path.join(out, 'browser-fallback.png')});
  assert.deepEqual(report.errors, []);
  report.result = 'pass';
} catch (error) {
  report.result = 'failed'; report.errors.push(error.stack ?? String(error)); process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  if (server) await server.close();
  if (renderer) await renderer.close({silent: true});
  await save();
}
console.log(JSON.stringify({out, result: report.result, stills: report.stills.length, browserFrames: report.browser.length, errors: report.errors}, null, 2));
