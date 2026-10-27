import type {RenderProps} from './types';

type ObjectValue = Record<string, unknown>;
function object(value: unknown, name: string): ObjectValue {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${name} must be an object`);
  return value as ObjectValue;
}
function text(value: unknown, name: string): asserts value is string {
  if (typeof value !== 'string') throw new Error(`${name} must be a string`);
}
function integer(value: unknown, name: string, min = 0): asserts value is number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min) throw new Error(`${name} must be an integer ≥ ${min}`);
}
function oneOf(value: unknown, choices: readonly unknown[], name: string) {
  if (!choices.includes(value)) throw new Error(`Invalid ${name}`);
}
function array(value: unknown, name: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${name} must be an array`);
  return value;
}
function positive(value: unknown, name: string): asserts value is number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) throw new Error(`${name} must be positive`);
}

/** Media can be same-origin or the documented localhost backend, never a CDN. */
export function localMediaPath(value: string): string {
  if (!value || value.startsWith('//') || value.includes('\\')) throw new Error('Invalid media path');
  const url = new URL(value, 'http://127.0.0.1');
  if (!['http:', 'https:'].includes(url.protocol) || !['127.0.0.1', 'localhost'].includes(url.hostname) || url.username || url.password) {
    throw new Error('Only same-origin paths or localhost media URLs are allowed');
  }
  return value;
}

/** Runtime boundary used by both the API client and the Node 24 render CLI. */
export function parseRenderProps(value: unknown): RenderProps {
  const props = object(value, 'props');
  const lesson = object(props.lesson, 'lesson');
  const timeline = object(props.timeline, 'timeline');
  oneOf(lesson.schema_version, ['1.0'], 'schema_version');
  oneOf(timeline.timeline_version, [1], 'timeline_version');
  const languages = ['en', 'hi', 'kn', 'ta', 'te', 'bn', 'mr'];
  oneOf(lesson.language, languages, 'language');
  if (lesson.language !== timeline.language || lesson.lesson_id !== timeline.lesson_id) throw new Error('Lesson/timeline identity mismatch');
  for (const key of ['lesson_id', 'topic', 'title', 'model', 'prompt_version']) text(lesson[key], `lesson.${key}`);
  oneOf(lesson.level, ['beginner', 'intermediate'], 'level');
  oneOf(lesson.source, ['llm', 'fallback', 'sample', 'edited'], 'source');
  oneOf(lesson.subject, ['programming', 'physics', 'chemistry', 'biology', 'math', 'other'], 'subject');
  integer(lesson.target_seconds, 'target_seconds', 30);
  if (lesson.target_seconds > 90) throw new Error('target_seconds exceeds 90');
  for (const key of ['warnings', 'keep_terms']) for (const item of array(lesson[key], key)) text(item, key);
  text(timeline.variant, 'variant');
  positive(timeline.tempo, 'tempo');
  const voice = object(timeline.voice, 'voice');
  text(voice.engine, 'voice.engine'); text(voice.voice_id, 'voice.voice_id'); positive(voice.speed, 'voice.speed');
  integer(timeline.fps, 'fps', 1);
  integer(timeline.duration_frames, 'duration_frames', 1);
  if (timeline.width !== 1280 || timeline.height !== 720) throw new Error('Expected a 1280×720 timeline');
  text(props.mediaBase, 'mediaBase');
  if (props.mediaBase) localMediaPath(props.mediaBase);
  oneOf(props.audioVariant, ['web', 'wav'], 'audioVariant');
  if (typeof props.showCaptions !== 'boolean') throw new Error('showCaptions must be a boolean');
  if (timeline.audio !== null) {
    const audio = object(timeline.audio, 'audio');
    for (const key of ['web', 'wav']) { text(audio[key], `audio.${key}`); localMediaPath(audio[key]); }
  }
  const scenes = array(lesson.scenes, 'lesson.scenes');
  const times = array(timeline.scenes, 'timeline.scenes');
  if (scenes.length < 3 || scenes.length > 6 || times.length !== scenes.length) throw new Error('Expected 3–6 matching scenes');
  const ids = new Set<string>();
  let end = 0;
  scenes.forEach((raw, index) => {
    const scene = object(raw, 'scene');
    const time = object(times[index], 'timeline scene');
    text(scene.id, 'scene.id'); text(scene.heading, 'heading'); text(scene.narration, 'narration');
    if (ids.has(scene.id)) throw new Error('Duplicate scene id');
    ids.add(scene.id);
    oneOf(scene.type, ['title_card', 'code_walkthrough', 'diagram', 'formula', 'recap'], 'scene type');
    if (index === 0 && scene.type !== 'title_card') throw new Error('First scene must be a title card');
    if (index > 0 && scene.type === 'title_card') throw new Error('Only one title card is allowed');
    const steps = array(scene.steps, 'steps');
    if (scene.type === 'title_card') {
      if (steps.length !== 0 || !scene.narration.trim()) throw new Error('Invalid title card');
      if (scene.subtitle !== undefined) text(scene.subtitle, 'subtitle');
    } else {
      const min = scene.type === 'diagram' || scene.type === 'recap' ? 2 : 1;
      const max = scene.type === 'diagram' ? 6 : scene.type === 'recap' ? 4 : 5;
      if (steps.length < min || steps.length > max) throw new Error('Invalid step count');
    }
    let codeLines = 0;
    if (scene.type === 'code_walkthrough') {
      text(scene.code, 'code');
      codeLines = scene.code.split('\n').length;
      if (!scene.code.trim() || codeLines > 12) throw new Error('Code must have 1–12 lines');
      oneOf(scene.code_language, ['python', 'javascript', 'java', 'c', 'cpp', 'other'], 'code_language');
    }
    if (scene.type === 'diagram') {
      oneOf(scene.layout, ['flow', 'cycle', 'labelled'], 'layout');
      if (scene.center !== undefined || scene.layout === 'labelled') text(scene.center, 'center');
    }
    if (scene.type === 'formula') text(scene.expression, 'expression');
    for (const rawStep of steps) {
      const step = object(rawStep, 'step');
      text(step.text, 'step.text'); text(step.narration, 'step.narration');
      if (!step.narration.trim()) throw new Error('Step narration cannot be empty');
      if (step.note !== undefined || scene.type === 'formula') text(step.note, 'note');
      if (step.output !== undefined) text(step.output, 'output');
      if (step.in_expression !== undefined && typeof step.in_expression !== 'boolean') throw new Error('Invalid in_expression');
      if (scene.type === 'code_walkthrough') {
        for (const line of array(step.lines, 'lines')) { integer(line, 'line', 1); if (line > codeLines) throw new Error('Highlight outside code'); }
      }
    }
    if (time.scene_id !== scene.id || time.type !== scene.type || time.start_frame !== end) throw new Error('Scene positions/identity do not match');
    integer(time.duration_frames, 'scene duration', 1);
    const sceneStart = end;
    end += time.duration_frames;
    let beatEnd = sceneStart;
    const stepIds = new Set<number>();
    let intros = 0;
    for (const rawBeat of array(time.beats, 'beats')) {
      const beat = object(rawBeat, 'beat');
      text(beat.beat_id, 'beat_id');
      integer(beat.start_frame, 'beat start'); integer(beat.end_frame, 'beat end', 1);
      if (beat.start_frame < beatEnd || beat.end_frame <= beat.start_frame || beat.end_frame > end) throw new Error('Beat outside scene or overlapping');
      beatEnd = beat.end_frame;
      if (beat.step_index === null) intros++;
      else {
        integer(beat.step_index, 'step_index');
        if (beat.step_index >= steps.length || stepIds.has(beat.step_index)) throw new Error('Invalid step beat');
        stepIds.add(beat.step_index);
      }
      let capEnd = beat.start_frame;
      for (const rawCap of array(beat.captions, 'captions')) {
        const cap = object(rawCap, 'caption');
        text(cap.text, 'caption.text'); integer(cap.start_frame, 'caption start'); integer(cap.end_frame, 'caption end', 1);
        if (cap.start_frame < capEnd || cap.end_frame <= cap.start_frame || cap.end_frame > beat.end_frame) throw new Error('Caption outside beat or overlapping');
        capEnd = cap.end_frame;
      }
    }
    if (stepIds.size !== steps.length || intros !== (scene.narration ? 1 : 0)) throw new Error('Missing or duplicate beats');
  });
  if (end !== timeline.duration_frames) throw new Error('Scene durations do not match the timeline');
  return value as RenderProps;
}
