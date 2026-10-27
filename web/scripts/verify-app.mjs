import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {chromium} from 'playwright-core';
import {config, health, job, lesson} from '../tests/api-fixtures.ts';

const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH ?? '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
const artifacts = new URL('../.validation/', import.meta.url);
await mkdir(artifacts, {recursive: true});
const errors = []; const external = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('request', (request) => {
  const url = new URL(request.url());
  if (['http:', 'https:'].includes(url.protocol) && !['127.0.0.1', 'localhost'].includes(url.hostname)) external.push(request.url());
});
let mode = 'unavailable'; let submissions = 0; let polls = 0; let lessonReads = 0;
let lastBody; let lastPoll = 0; let minPollGap = Infinity;
await page.route('**/api/**', async (route) => {
  const path = new URL(route.request().url()).pathname;
  if (mode === 'unavailable') return route.abort();
  const respond = (value, status = 200) => route.fulfill({status, contentType: 'application/json', body: JSON.stringify(value)});
  if (path === '/api/health') return respond(health);
  if (path === '/api/config') return respond(config);
  if (path === '/api/lessons' && route.request().method() === 'POST') {
    submissions++; lastBody = route.request().postDataJSON();
    if (mode === '422' || mode === '500') return respond({error: {code: 'contract_error', message: `Test ${mode} error`}}, Number(mode));
    return respond({job_id: job.job_id, lesson_id: lesson.lesson_id, variant: lesson.variant, cached: mode === 'cached'}, 202);
  }
  if (path.startsWith('/api/jobs/')) {
    const now = performance.now(); if (lastPoll) minPollGap = Math.min(minPollGap, now - lastPoll); lastPoll = now;
    polls++;
    if (mode === '404') return respond({error: {code: 'not_found', message: 'Test job not found'}}, 404);
    if (mode === 'job-error') return respond({...job, status: 'error', error: 'Test job failed'});
    const done = mode === 'cached' || polls >= 5;
    const playable = done || polls >= 2;
    return respond({...job, playable, status: done ? 'done' : 'running', fallback: mode === 'fallback',
      fallback_reason: mode === 'fallback' ? 'Test fallback reason.' : null,
      stages: job.stages.map((stage) => stage.name === 'export' && done ? {...stage, status: 'done', ms: 100} : stage)});
  }
  if (path.startsWith('/api/lessons/')) {
    lessonReads++;
    const finished = mode === 'cached' || polls >= 5;
    return respond({...lesson, media: {...lesson.media, mp4: finished ? '/media/test/lesson.mp4' : null}});
  }
  return respond({error: {code: 'not_found', message: 'Unknown test route'}}, 404);
});
async function home() {
  await page.goto('http://127.0.0.1:5173/');
  await page.getByRole('heading', {name: 'Make the “why” click.'}).waitFor();
}
try {
  await home();
  await page.getByText('Local backend unavailable', {exact: true}).waitFor();
  assert.equal(await page.getByRole('button', {name: 'Generate animated lesson'}).isDisabled(), true);
  await page.screenshot({path: new URL('app-desktop.png', artifacts).pathname, fullPage: true});
  for (const id of ['python', 'newton', 'water']) {
    await page.goto(`http://127.0.0.1:5173/#/sample/${id}`);
    await page.getByRole('region', {name: 'Lesson player'}).waitFor();
    assert.ok((await page.getByText('Hand-written sample · no AI generation or narration.').textContent()).includes('Hand-written'));
    await page.getByRole('button', {name: 'Play', exact: true}).click();
    await page.getByRole('button', {name: 'Pause', exact: true}).waitFor();
    await page.getByRole('button', {name: 'Pause', exact: true}).click();
    await page.getByRole('button', {name: 'Next scene', exact: true}).click();
    await page.getByText('Scene 2 / 4', {exact: true}).waitFor();
    await page.getByRole('button', {name: 'Previous scene', exact: true}).click();
    await page.getByText('Scene 1 / 4', {exact: true}).waitFor();
    await page.getByRole('button', {name: 'Captions', exact: true}).click();
    assert.equal(await page.getByRole('button', {name: 'Captions', exact: true}).getAttribute('aria-pressed'), 'false');
    await page.getByRole('button', {name: 'Replay lesson', exact: true}).click();
    await page.getByRole('button', {name: 'Pause', exact: true}).click();
    const download = page.waitForEvent('download'); await page.getByRole('link', {name: '↓ SRT', exact: true}).click();
    assert.ok((await download).suggestedFilename().endsWith('.srt'));
  }
  await page.setViewportSize({width: 390, height: 844}); await home();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.screenshot({path: new URL('app-mobile.png', artifacts).pathname, fullPage: true});
  await page.goto('http://127.0.0.1:5173/#/sample/python');
  await page.getByRole('region', {name: 'Lesson player'}).waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.screenshot({path: new URL('player-mobile.png', artifacts).pathname, fullPage: true});
  await page.setViewportSize({width: 1440, height: 1100});
  mode = 'success'; await home();
  await page.getByText('Local backend ready', {exact: true}).waitFor();
  const generate = page.getByRole('button', {name: 'Generate animated lesson'});
  await page.getByLabel('Your topic', {exact: true}).press('Enter'); await page.getByRole('alert').filter({hasText: 'Type a topic first'}).waitFor();
  assert.equal(submissions, 0);
  await page.getByLabel('Your topic', {exact: true}).fill('  Python loops  ');
  await page.getByLabel('Language', {exact: true}).selectOption('hi');
  await generate.dblclick();
  await page.getByRole('region', {name: 'Lesson player'}).waitFor();
  assert.equal(submissions, 1); assert.equal(lastBody.topic, 'Python loops'); assert.equal(lastBody.language, 'hi');
  assert.equal(lastBody.target_seconds, 60);
  assert.ok(await page.getByRole('button', {name: /MP4 · rendering/}).isDisabled());
  await page.getByRole('link', {name: '↓ MP4', exact: true}).waitFor();
  assert.equal(lessonReads, 2); assert.ok(minPollGap >= 450);
  const completedPolls = polls;
  await page.waitForTimeout(650); assert.equal(polls, completedPolls, 'Completed jobs must stop polling');
  await page.reload(); await page.getByRole('region', {name: 'Lesson player'}).waitFor();
  for (const scenario of ['422', '500']) {
    mode = scenario; await home(); await page.getByText('Local backend ready', {exact: true}).waitFor();
    await page.getByLabel('Your topic', {exact: true}).fill('Python loops'); await generate.click();
    await page.getByRole('alert').filter({hasText: `Test ${scenario} error`}).waitFor();
  }
  for (const scenario of ['404', 'job-error', 'fallback', 'cached']) {
    mode = scenario; polls = 0; lastPoll = 0;
    await page.goto(`http://127.0.0.1:5173/#/job/${job.job_id}`);
    if (scenario === '404' || scenario === 'job-error') await page.getByRole('alert').filter({hasText: scenario === '404' ? 'Test job not found' : 'Test job failed'}).waitFor();
    else {
      await page.getByRole('region', {name: 'Lesson player'}).waitFor();
      if (scenario === 'fallback') await page.getByText(/Test fallback reason/).waitFor();
    }
    await page.getByRole('link', {name: 'Blu VisualTeacher home', exact: true}).click();
    const before = polls; await page.waitForTimeout(650); assert.equal(polls, before, 'Leaving a job must cancel polling');
  }
  assert.deepEqual(errors, []); assert.deepEqual(external, []);
  console.log('PASS: offline sample UI; desktop/mobile; player controls; SRT; validation; contract submission; playable before MP4; export completion; reload; cached/fallback/error cases; polling cleanup; no external requests.');
} finally {await browser.close();}
