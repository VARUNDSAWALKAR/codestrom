import {useEffect, useState, type FormEvent} from 'react';
import type {AppConfig, CreateLessonRequest, Health, Level, Voice} from './api';
import type {Language} from '../lesson/types';

const defaultInput: CreateLessonRequest = {topic: '', level: 'beginner', language: 'en', target_seconds: 60, voice: 'female', speed: 1};
const coreLanguages = [{code: 'en', name: 'English', native: 'English', available: true},
  {code: 'hi', name: 'Hindi', native: 'हिन्दी', available: true}, {code: 'kn', name: 'Kannada', native: 'ಕನ್ನಡ', available: true}];
const examples = ['Python Loops', "Newton’s Second Law", 'Water Cycle', 'Binary Search', 'Photosynthesis'];
const capitalize = (text: string) => `${text[0]?.toUpperCase()}${text.slice(1)}`;

export function CreateForm({config, health, busy, onSubmit}: {
  config: AppConfig | null; health: Health | null; busy: boolean; onSubmit: (input: CreateLessonRequest) => void;
}) {
  const [input, setInput] = useState(defaultInput);
  const [error, setError] = useState('');
  useEffect(() => { if (config) setInput((previous) => ({...previous, ...config.defaults, target_seconds: config.target_seconds.default})); }, [config]);
  const validate = () => input.topic.trim().length < 3 ? 'Type a topic first (at least 3 characters).' : input.topic.trim().length > 120 ? 'Keep your topic to 120 characters.' : '';
  const submit = (event: FormEvent) => {
    event.preventDefault(); const message = validate(); setError(message);
    if (message || !health?.ok || !config || busy) return;
    if (!config.languages.some((language) => language.code === input.language && language.available)) {setError('Choose an available language.'); return;}
    onSubmit({...input, topic: input.topic.trim()});
  };
  const duration = config?.target_seconds ?? {min: 30, max: 90, step: 15, default: 60};
  const durations = Array.from({length: Math.floor((duration.max - duration.min) / duration.step) + 1}, (_, i) => duration.min + i * duration.step);
  return <form className="create-form" onSubmit={submit} noValidate aria-label="Create your lesson">
    <div className="section-heading"><div><span className="eyebrow">A LITTLE CURIOSITY GOES A LONG WAY</span><h2>Create your lesson</h2></div>
      <span className="form-title-icon" aria-hidden="true">✧</span></div>
    <label htmlFor="topic">What would you like to understand?</label>
    <div className="topic-field"><span className="topic-sparkle" aria-hidden="true">✧</span>
      <textarea id="topic" name="topic" rows={3} maxLength={120} placeholder="e.g. Explain how a Python for loop works"
        aria-describedby={`topic-help${error ? ' topic-error' : ''}`} aria-invalid={Boolean(error)} value={input.topic}
        onKeyDown={(event) => {if (event.key === 'Enter' && !event.shiftKey) {event.preventDefault(); event.currentTarget.form?.requestSubmit();}}}
        onChange={(event) => {setInput({...input, topic: event.target.value}); setError('');}} onBlur={() => {if (input.topic) setError(validate());}} />
    </div>
    <div className="field-help"><span id="topic-help">Start with a question, a topic, or a big idea.</span><span>{input.topic.length}/120</span></div>
    {error && <p id="topic-error" role="alert" className="field-error">{error}</p>}
    <div className="example-chips" aria-label="Example topics">{examples.map((topic) => <button key={topic} type="button" onClick={() => {setInput({...input, topic}); setError('');}}>{topic}</button>)}</div>
    <div className="form-grid">
      <fieldset className="setting-group"><legend>Difficulty</legend><div className="segmented-control">
        {(config?.levels ?? ['beginner', 'intermediate']).map((level) => <label className={`segment-option ${input.level === level ? 'is-selected' : ''}`} key={level}>
          <input type="radio" name="level" value={level} checked={input.level === level} onChange={() => setInput({...input, level: level as Level})} /><span>{capitalize(level)}</span>
        </label>)}</div></fieldset>
      <fieldset className="setting-group"><legend>Language</legend><div className="segmented-control language-options">
        {(config?.languages ?? coreLanguages).map((language) => <label className={`segment-option ${input.language === language.code ? 'is-selected' : ''}`} key={language.code}
          title={language.available ? language.name : `${language.name} is unavailable on this backend`}>
          <input type="radio" name="language" value={language.code} checked={input.language === language.code} disabled={!language.available}
            onChange={() => setInput({...input, language: language.code as Language})} /><span lang={language.code}>{language.native}</span>
        </label>)}</div></fieldset>
      <fieldset className="setting-group duration-group"><legend>Lesson duration <span className="setting-hint">A little time. A clearer picture.</span></legend>
        <div className="segmented-control duration-options">{durations.map((seconds) => <label className={`segment-option ${input.target_seconds === seconds ? 'is-selected' : ''}`} key={seconds}>
          <input type="radio" name="target_seconds" value={seconds} checked={input.target_seconds === seconds} onChange={() => setInput({...input, target_seconds: seconds})} /><span>{seconds} sec</span>
        </label>)}</div></fieldset>
      <fieldset className="setting-group"><legend>Narration voice</legend><div className="segmented-control voice-options">
        {(config?.voices ?? ['female', 'male']).map((voice) => <label className={`segment-option ${input.voice === voice ? 'is-selected' : ''}`} key={voice}>
          <input type="radio" name="voice" value={voice} checked={input.voice === voice} onChange={() => setInput({...input, voice: voice as Voice})} /><span>{capitalize(voice)}</span>
        </label>)}</div></fieldset>
    </div>
    <details className="advanced-settings"><summary>More options</summary><label>Speech speed<select aria-label="Speech speed" value={input.speed} onChange={(event) => setInput({...input, speed: Number(event.target.value)})}>
      {(config?.speeds ?? [0.85, 1, 1.15]).map((speed) => <option key={speed} value={speed}>{speed}×{speed === 1 ? ' · Natural' : speed < 1 ? ' · Slower' : ' · Faster'}</option>)}</select></label></details>
    <button className="button primary generate" type="submit" disabled={!health?.ok || !config || busy} aria-describedby="generation-help">
      <span aria-hidden="true">✧</span> {busy ? 'Submitting…' : 'Generate Visual Lesson'} <span aria-hidden="true">→</span></button>
    <p className="privacy-note"><span aria-hidden="true">⌑</span> Runs locally · Your lesson stays private</p>
    <p id="generation-help" className="form-footnote backend-hint">{health?.ok && config ? 'Your local AI is ready. Let’s make something click.' : 'Connect the local backend to generate. You can explore the sample lessons now.'}</p>
  </form>;
}
