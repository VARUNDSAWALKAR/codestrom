import type {Language, Lesson, Timeline} from '../lesson/types';
import {localMediaPath, parseRenderProps} from '../lesson/validate';

export type Level = 'beginner' | 'intermediate';
export type Voice = 'female' | 'male';
export interface Health {
  ok: boolean; device_profile: 'gpu' | 'cpu'; offline: boolean;
  models: {planner: {name: string; ready: boolean}; translator: {name: string; ready: boolean};
    tts_kokoro: {ready: boolean}; tts_parler: {ready: boolean; enabled: boolean}};
  renderer: {bundle_ready: boolean}; queue_length: number;
}
export interface AppConfig {
  languages: {code: Language; name: string; native: string; tier: 'core' | 'bonus'; available: boolean}[];
  levels: Level[];
  target_seconds: {min: number; max: number; step: number; default: number};
  voices: Voice[]; speeds: number[];
  defaults: {language: Language; level: Level; voice: Voice; speed: number};
}
export interface CreateLessonRequest {
  topic: string; level: Level; language: Language; target_seconds: number; voice: Voice; speed: number;
}
export interface CreateLessonResponse {job_id: string; lesson_id: string; variant: string; cached: boolean}
export type StageName = 'plan' | 'validate' | 'translate' | 'voice' | 'timeline' | 'export';
export interface Stage {
  name: StageName; status: 'pending' | 'running' | 'done' | 'cached' | 'skipped' | 'error';
  ms: number | null; rss_mb: number | null; note: string;
}
export interface Job {
  job_id: string; kind: 'create' | 'revoice' | 'edit'; status: 'queued' | 'running' | 'done' | 'error';
  queue_position: number; lesson_id: string; variant: string; playable: boolean;
  fallback: boolean; fallback_reason: string | null; progress: number; stages: Stage[];
  warnings: string[]; error: string | null; total_ms: number; device_profile: 'gpu' | 'cpu';
}
export interface LessonResponse {
  lesson_id: string; variant: string; lesson: Lesson; timeline: Timeline;
  media: {audio_web: string | null; audio_wav: string | null; mp4: string | null; srt: string | null};
  meta: {source: Lesson['source']; model: string; warnings: string[]; stage_ms: Partial<Record<StageName, number>>; variants: string[]};
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public code: string) { super(message); this.name = 'ApiError'; }
}
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Backend returned an invalid object');
  return value as Record<string, unknown>;
}
const string = (value: unknown): value is string => typeof value === 'string';
const number = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const boolean = (value: unknown): value is boolean => typeof value === 'boolean';
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(string);
function check(condition: unknown): asserts condition {
  if (!condition) throw new Error('Backend response does not match the API contract');
}
async function request(path: string, signal?: AbortSignal, body?: CreateLessonRequest): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(path, {method: body ? 'POST' : 'GET',
      headers: {Accept: 'application/json', ...(body ? {'Content-Type': 'application/json'} : {})},
      ...(body ? {body: JSON.stringify(body)} : {}),
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(10000)]) : AbortSignal.timeout(10000)});
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError('Cannot reach the local backend. Check that it is running, then retry.', 0, 'network');
  }
  const value: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    let message = response.status === 422 ? 'The backend rejected the lesson settings. Check your input.' :
      response.status === 404 ? 'This lesson or job could not be found.' : `The backend returned an error (${response.status}).`;
    let code = 'http_error';
    if (value && typeof value === 'object' && 'error' in value && value.error && typeof value.error === 'object') {
      if ('message' in value.error && string(value.error.message)) message = value.error.message;
      if ('code' in value.error && string(value.error.code)) code = value.error.code;
    }
    throw new ApiError(message, response.status, code);
  }
  return value;
}

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const v = record(await request('/api/health', signal));
  const models = record(v.models);
  check(boolean(v.ok) && boolean(v.offline) && ['gpu', 'cpu'].includes(String(v.device_profile)) && number(v.queue_length));
  for (const name of ['planner', 'translator', 'tts_kokoro', 'tts_parler']) check(boolean(record(models[name]).ready));
  check(boolean(record(models.tts_parler).enabled) && boolean(record(v.renderer).bundle_ready));
  return v as unknown as Health;
}
export async function getConfig(signal?: AbortSignal): Promise<AppConfig> {
  const v = record(await request('/api/config', signal));
  const languages: readonly string[] = ['en', 'hi', 'kn', 'ta', 'te', 'bn', 'mr'];
  check(Array.isArray(v.languages) && v.languages.length > 0);
  for (const raw of v.languages) {
    const lang = record(raw);
    check(languages.includes(String(lang.code)) && string(lang.name) && string(lang.native) && boolean(lang.available) && ['core', 'bonus'].includes(String(lang.tier)));
  }
  check(strings(v.levels) && v.levels.length > 0 && v.levels.every((level) => ['beginner', 'intermediate'].includes(level)));
  check(strings(v.voices) && v.voices.length > 0 && v.voices.every((voice) => ['female', 'male'].includes(voice)));
  check(Array.isArray(v.speeds) && v.speeds.length > 0 && v.speeds.every((speed) => number(speed) && speed >= 0.8 && speed <= 1.2));
  const seconds = record(v.target_seconds);
  check(number(seconds.min) && number(seconds.max) && number(seconds.step) && number(seconds.default) &&
    seconds.min >= 30 && seconds.max <= 90 && seconds.max >= seconds.min && seconds.step > 0 &&
    seconds.default >= seconds.min && seconds.default <= seconds.max);
  const defaults = record(v.defaults);
  check(languages.includes(String(defaults.language)) && v.levels.includes(String(defaults.level)) && v.voices.includes(String(defaults.voice)) && v.speeds.includes(defaults.speed));
  return v as unknown as AppConfig;
}
export async function createLesson(input: CreateLessonRequest, signal?: AbortSignal): Promise<CreateLessonResponse> {
  const v = record(await request('/api/lessons', signal, {...input, topic: input.topic.trim()}));
  check(string(v.job_id) && string(v.lesson_id) && string(v.variant) && boolean(v.cached));
  return v as unknown as CreateLessonResponse;
}
export async function getJob(id: string, signal?: AbortSignal): Promise<Job> {
  const v = record(await request(`/api/jobs/${encodeURIComponent(id)}`, signal));
  check(string(v.job_id) && string(v.lesson_id) && string(v.variant) && ['queued', 'running', 'done', 'error'].includes(String(v.status)) &&
    ['create', 'revoice', 'edit'].includes(String(v.kind)) && boolean(v.playable) && boolean(v.fallback) &&
    (v.fallback_reason === null || string(v.fallback_reason)) && (v.error === null || string(v.error)) &&
    number(v.progress) && v.progress >= 0 && v.progress <= 1 && number(v.total_ms) && number(v.queue_position) &&
    strings(v.warnings) && ['cpu', 'gpu'].includes(String(v.device_profile)) && Array.isArray(v.stages));
  for (const raw of v.stages) {
    const stage = record(raw);
    check(['plan', 'validate', 'translate', 'voice', 'timeline', 'export'].includes(String(stage.name)) &&
      ['pending', 'running', 'done', 'cached', 'skipped', 'error'].includes(String(stage.status)) &&
      (stage.ms === null || number(stage.ms)) && (stage.rss_mb === null || number(stage.rss_mb)) && string(stage.note));
  }
  return v as unknown as Job;
}
export async function getLesson(id: string, variant?: string, signal?: AbortSignal): Promise<LessonResponse> {
  const query = variant ? `?variant=${encodeURIComponent(variant)}` : '';
  const v = record(await request(`/api/lessons/${encodeURIComponent(id)}${query}`, signal));
  check(string(v.lesson_id) && string(v.variant));
  const props = parseRenderProps({lesson: v.lesson, timeline: v.timeline, mediaBase: '', audioVariant: 'web', showCaptions: true});
  check(props.lesson.lesson_id === v.lesson_id && props.timeline.variant === v.variant);
  const media = record(v.media);
  for (const key of ['audio_web', 'audio_wav', 'mp4', 'srt']) {
    const value = media[key]; check(value === null || string(value)); if (string(value)) localMediaPath(value);
  }
  const meta = record(v.meta);
  check(['llm', 'sample', 'fallback', 'edited'].includes(String(meta.source)) && string(meta.model) && strings(meta.warnings) && strings(meta.variants));
  record(meta.stage_ms);
  return v as unknown as LessonResponse;
}

export function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(signal.reason); return; }
    const abort = () => { clearTimeout(timer); reject(signal.reason); };
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, ms);
    signal.addEventListener('abort', abort, {once: true});
  });
}
