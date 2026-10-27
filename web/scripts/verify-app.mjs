import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {chromium} from 'playwright-core';
import {config, health, job, lesson} from '../tests/api-fixtures.ts';

const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH ?? '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
const artifacts = new URL('../.validation/', import.meta.url); await mkdir(artifacts, {recursive: true});
const errors = []; const external = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('request', (request) => {const url = new URL(request.url()); if (['http:', 'https:'].includes(url.protocol) && !['127.0.0.1', 'localhost'].includes(url.hostname)) external.push(request.url());});

let mode = 'unavailable'; let submissions = 0; let polls = 0; let lessonReads = 0; let rateLimits = 0;
let lastBody; let lastPoll = 0; let minPollGap = Infinity;
await page.route('**/api/**', async (route) => {
  const path = new URL(route.request().url()).pathname;
  if (mode === 'unavailable') return route.abort();
  const respond = (value, status = 200, headers = {}) => route.fulfill({status, headers, contentType: 'application/json', body: JSON.stringify(value)});
  if (path === '/api/health') return respond({...health, ok: false, mock_pipeline: mode === 'mock', models: {...health.models,
    translator: {...health.models.translator, ready: false}, tts_kokoro: {ready: false}}});
  if (path === '/api/config') return respond(config);
  if (path === '/api/lessons' && route.request().method() === 'POST') {
    submissions++; lastBody = route.request().postDataJSON();
    if (mode === '422') return respond({error: {code: 'validation_error', message: 'Check the highlighted fields.', fields: [{field: 'topic', message: 'Choose a supported topic.'}]}}, 422);
    if (mode === '429' && rateLimits++ === 0) return respond({error: {code: 'busy', message: 'Queue busy', retry_after: 0}}, 429, {'Retry-After': '0'});
    if (mode === '500') return respond({error: {code: 'contract_error', message: 'Test 500 error'}}, 500);
    return respond({job_id: job.job_id, lesson_id: lesson.lesson_id, variant: lesson.variant, cached: mode === 'cached', mock: mode === 'mock'}, 202);
  }
  if (path.startsWith('/api/jobs/')) {
    const now = performance.now(); if (lastPoll) minPollGap = Math.min(minPollGap, now - lastPoll); lastPoll = now; polls++;
    if (mode === '404') return respond({error: {code: 'not_found', message: 'Test job not found'}}, 404);
    if (mode === 'job-error') return respond({...job, status: 'error', error: 'Planner stopped', error_detail: {stage: 'plan', code: 'planner_failed', message: 'The planner could not create this lesson.'}});
    if (mode === 'export-failed') return respond({...job, playable: true, preview_ready: true, status: 'error', export_status: 'failed', error: 'Renderer failed', error_detail: {stage: 'export', code: 'render_failed', message: 'Renderer failed'}});
    const done = mode === 'cached' || polls >= 5; const previewReady = done || polls >= 2;
    return respond({...job, playable: previewReady, preview_ready: previewReady, status: done ? 'done' : 'running', export_status: done ? 'completed' : previewReady ? 'running' : 'pending', mock: mode === 'mock', progress: done ? 1 : previewReady ? .42 : .12,
      stages: job.stages.map((stage) => stage.name === 'export' ? {...stage, status: done ? 'done' : previewReady ? 'running' : 'pending', ms: done ? 100 : null} : stage)});
  }
  if (path.startsWith('/api/lessons/')) {
    lessonReads++; const failed = mode === 'export-failed'; const finished = mode === 'cached' || polls >= 5;
    return respond({...lesson, mock: mode === 'mock', export_status: failed ? 'failed' : finished ? 'completed' : 'running', media: {...lesson.media, mp4: finished && !failed ? '/media/test/lesson.mp4' : null}});
  }
  return respond({error: {code: 'not_found', message: 'Unknown test route'}}, 404);
});

async function home() {await page.goto('http://127.0.0.1:5173/'); await page.getByRole('heading', {name: 'Turn any concept into a visual lesson.'}).waitFor();}
async function submitTopic(topic = 'Python loop') {await page.getByLabel('What would you like to understand?', {exact: true}).fill(topic); await page.getByRole('button', {name: 'Generate Visual Lesson'}).click();}

try {
  await home(); await page.getByText('Local backend unavailable', {exact: true}).waitFor();
  assert.equal(await page.getByRole('button', {name: 'Generate Visual Lesson'}).isDisabled(), true);
  await page.screenshot({path: new URL('app-desktop.png', artifacts).pathname, fullPage: true});
  await page.goto('http://127.0.0.1:5173/#/about'); await page.getByRole('heading', {name: 'A clearer way to learn.'}).waitFor();
  await page.goto('http://127.0.0.1:5173/#/library'); await page.getByText('This page does not exist.', {exact: false}).waitFor();

  for (const id of ['python', 'newton', 'water']) {
    await page.goto(`http://127.0.0.1:5173/#/sample/${id}`); await page.getByRole('region', {name: 'Lesson player'}).waitFor();
    await page.getByRole('button', {name: 'Next scene'}).click(); await page.getByText('Scene 2 of 4 · Click a chapter to jump in', {exact: true}).waitFor();
    await page.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : undefined));
    await page.keyboard.press('c'); assert.equal(await page.getByRole('button', {name: 'Captions'}).getAttribute('aria-pressed'), 'false');
    await page.getByLabel('Playback speed').selectOption('1.25'); assert.equal(await page.getByLabel('Playback speed').inputValue(), '1.25');
    assert.equal(await page.getByRole('slider', {name: 'Narration volume'}).isDisabled(), true);
    if (id === 'python') await page.screenshot({path: new URL('player-desktop.png', artifacts).pathname, fullPage: true});
  }

  await page.setViewportSize({width: 320, height: 800}); await home(); assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.setViewportSize({width: 390, height: 844}); await page.screenshot({path: new URL('app-mobile.png', artifacts).pathname, fullPage: true}); await page.setViewportSize({width: 1440, height: 1100});

  mode = 'success'; await home(); await page.getByText('Local planner ready', {exact: true}).waitFor();
  assert.equal(await page.getByRole('button', {name: 'Generate Visual Lesson'}).isDisabled(), false);
  assert.equal(await page.getByRole('radio', {name: 'हिन्दी'}).isDisabled(), true); assert.equal(await page.getByRole('radio', {name: 'ಕನ್ನಡ'}).isDisabled(), true);
  await page.locator('summary', {hasText: 'More options'}).click(); await page.getByLabel('Subject').selectOption('programming');
  polls = 0; lessonReads = 0; submissions = 0; lastPoll = 0; minPollGap = Infinity; await submitTopic('  Python loop  ');
  await page.getByRole('region', {name: 'Generation progress'}).waitFor(); await page.getByRole('region', {name: 'Lesson player'}).waitFor();
  assert.equal(submissions, 1); assert.equal(lastBody.topic, 'Python loop'); assert.equal(lastBody.language, 'en'); assert.equal(lastBody.subject, 'programming');
  assert.ok(await page.getByRole('button', {name: /Rendering 42%/}).isDisabled()); await page.getByRole('link', {name: 'Download MP4'}).waitFor();
  assert.equal(await page.getByRole('link', {name: 'Download MP4'}).getAttribute('href'), '/media/test/lesson.mp4'); assert.equal(lessonReads, 2); assert.ok(minPollGap >= 450);
  const completedPolls = polls; await page.waitForTimeout(650); assert.equal(polls, completedPolls); await page.reload(); await page.getByRole('region', {name: 'Lesson player'}).waitFor();

  mode = '422'; await home(); await submitTopic(); await page.getByText('Choose a supported topic.', {exact: true}).waitFor();
  mode = '429'; rateLimits = 0; polls = 0; await home(); await submitTopic(); await page.getByRole('region', {name: 'Generation progress'}).waitFor(); assert.equal(rateLimits, 2);
  mode = 'job-error'; polls = 0; await page.goto(`http://127.0.0.1:5173/#/job/${job.job_id}`);
  await page.getByRole('alert').filter({hasText: 'Failed during plan: The planner could not create this lesson.'}).waitFor(); assert.equal(await page.getByRole('link', {name: 'Use Sample Lesson'}).count(), 0);
  await page.getByRole('button', {name: 'Try Again'}).click(); await page.getByRole('heading', {name: 'Create your lesson'}).waitFor();
  assert.equal(await page.getByLabel('What would you like to understand?').inputValue(), 'Python loop');
  mode = 'export-failed'; polls = 0; await page.goto(`http://127.0.0.1:5173/#/job/${job.job_id}`); await page.getByRole('region', {name: 'Lesson player'}).waitFor(); await page.getByText('Video export failed', {exact: true}).waitFor();
  mode = 'mock'; polls = 0; await home(); await page.getByText('MOCK MODE', {exact: true}).waitFor(); await page.goto(`http://127.0.0.1:5173/#/job/${job.job_id}`); await page.getByText('MOCK MODE', {exact: true}).waitFor();
  assert.deepEqual(errors, []); assert.deepEqual(external, []);
  console.log('PASS: English-only creation; planner gating; field and retry errors; 500ms preview/export polling; direct downloads; export failure; mock banner; player controls; route restore; responsive layout; no external requests.');
} finally {await browser.close();}
