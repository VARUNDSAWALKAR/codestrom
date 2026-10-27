import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ApiError, createLesson, getConfig, getHealth, getJob, getLesson, wait} from '../src/app/api';
import {config, health, job, lesson} from './api-fixtures';

test('typed API client preserves paths and snake_case request/response fields', async () => {
  const original = globalThis.fetch;
  const calls: {url: string; body?: string}[] = [];
  globalThis.fetch = async (url, options) => {
    calls.push({url: String(url), ...(typeof options?.body === 'string' ? {body: options.body} : {})});
    const result = String(url) === '/api/health' ? health : String(url) === '/api/config' ? config :
      String(url).startsWith('/api/jobs/') ? job : options?.method === 'POST' ?
        {job_id: job.job_id, lesson_id: lesson.lesson_id, variant: lesson.variant, cached: false, mock: false} : lesson;
    return Response.json(result);
  };
  try {
    assert.deepEqual(await getHealth(), health); assert.deepEqual(await getConfig(), config);
    const result = await createLesson({topic: '  Python loops  ', level: 'beginner', language: 'en', target_seconds: 60, voice: 'female', speed: 1});
    assert.equal(result.job_id, job.job_id);
    assert.equal(JSON.parse(calls.at(-1)!.body!).topic, 'Python loops');
    assert.deepEqual(await getJob('a/b'), job);
    assert.equal(calls.at(-1)?.url, '/api/jobs/a%2Fb');
    assert.deepEqual(await getLesson(lesson.lesson_id, lesson.variant), lesson);
    assert.equal(calls.at(-1)?.url, `/api/lessons/${lesson.lesson_id}?variant=en-female-1`);
  } finally {globalThis.fetch = original;}
});
for (const status of [404, 422, 500]) test(`API ${status} remains an explicit error`, async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => Response.json({error: {code: 'test_error', message: 'Contract error'}}, {status});
  try {await assert.rejects(getHealth(), (error: unknown) => error instanceof ApiError && error.status === status && error.message === 'Contract error');}
  finally {globalThis.fetch = original;}
});
test('network failures and malformed successful payloads do not become fake success', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => {throw new TypeError('network');};
    await assert.rejects(getHealth(), (error: unknown) => error instanceof ApiError && error.code === 'network');
    globalThis.fetch = async () => Response.json({ok: true});
    await assert.rejects(getHealth());
  } finally {globalThis.fetch = original;}
});
test('poll delay is abortable so navigation cancels pending work', async () => {
  const controller = new AbortController();
  const pending = wait(10000, controller.signal); controller.abort();
  await assert.rejects(pending);
});
test('422 errors retain field validation details', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => Response.json({error: {code: 'validation_error', message: 'Invalid lesson',
    fields: [{field: 'topic', message: 'Choose a supported topic.'}]}}, {status: 422});
  try {await assert.rejects(createLesson({topic: 'Unsupported', level: 'beginner', language: 'en', target_seconds: 60, voice: 'female', speed: 1}),
    (error: unknown) => error instanceof ApiError && error.fields[0]?.field === 'topic');}
  finally {globalThis.fetch = original;}
});
test('429 responses retry automatically using Retry-After', async () => {
  const original = globalThis.fetch; let attempts = 0;
  globalThis.fetch = async () => {
    attempts++;
    if (attempts === 1) return Response.json({error: {code: 'busy', message: 'Queue busy'}}, {status: 429, headers: {'Retry-After': '0'}});
    return Response.json({...health});
  };
  try {assert.deepEqual(await getHealth(), health); assert.equal(attempts, 2);}
  finally {globalThis.fetch = original;}
});
