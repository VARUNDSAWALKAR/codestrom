import type {AppConfig, Health, Job, LessonResponse} from '../src/app/api';
import {sampleProps} from '../src/remotion/sampleProps';

// Contract fixtures for tests only. These are never a live backend substitute.
export const health: Health = {ok: true, mock_pipeline: false, device_profile: 'cpu', offline: true,
  models: {planner: {name: 'test-planner', ready: true}, translator: {name: 'test-translator', ready: true},
    tts_kokoro: {ready: true}, tts_parler: {ready: false, enabled: false}}, renderer: {bundle_ready: true}, queue_length: 0};
export const config: AppConfig = {languages: [
  {code: 'en', name: 'English', native: 'English', tier: 'core', available: true},
  {code: 'hi', name: 'Hindi', native: 'हिन्दी', tier: 'core', available: true},
  {code: 'kn', name: 'Kannada', native: 'ಕನ್ನಡ', tier: 'core', available: true},
  {code: 'ta', name: 'Tamil', native: 'தமிழ்', tier: 'bonus', available: false}],
  levels: ['beginner', 'intermediate'], target_seconds: {min: 30, max: 90, step: 15, default: 60},
  voices: ['female', 'male'], speeds: [0.85, 1, 1.15], defaults: {language: 'en', level: 'beginner', voice: 'female', speed: 1}};
export const job: Job = {job_id: 'contract-job', kind: 'create', status: 'running', queue_position: 0,
  lesson_id: sampleProps.lesson.lesson_id, variant: sampleProps.timeline.variant, playable: false, preview_ready: false,
  export_status: 'running', mock: false, progress: 0.2, stages: [
    {name: 'plan', status: 'done', ms: 10, rss_mb: 10, note: 'Test fixture'},
    {name: 'validate', status: 'done', ms: 2, rss_mb: 10, note: ''},
    {name: 'translate', status: 'skipped', ms: 0, rss_mb: 10, note: ''},
    {name: 'voice', status: 'done', ms: 2, rss_mb: 10, note: ''},
    {name: 'timeline', status: 'done', ms: 2, rss_mb: 10, note: ''},
    {name: 'export', status: 'running', ms: null, rss_mb: null, note: ''}],
  warnings: [], error: null, error_detail: null, total_ms: 16, device_profile: 'cpu'};
export const lesson: LessonResponse = {lesson_id: sampleProps.lesson.lesson_id, variant: sampleProps.timeline.variant,
  preview_ready: true, export_status: 'completed', mock: false,
  lesson: sampleProps.lesson, timeline: sampleProps.timeline,
  media: {audio_web: null, audio_wav: null, mp4: null, srt: null},
  meta: {source: 'sample', model: 'hand-written', warnings: [], stage_ms: {}, variants: [sampleProps.timeline.variant]}};
