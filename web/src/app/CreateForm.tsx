import {useEffect, useState, type FormEvent} from 'react';
import type {AppConfig, CreateLessonRequest, Health, Level, Voice} from './api';
import type {Language} from '../lesson/types';

const defaultInput: CreateLessonRequest = {topic: '', level: 'beginner', language: 'en', target_seconds: 60, voice: 'female', speed: 1};
const coreLanguages = [{code: 'en', name: 'English', native: 'English', available: true},
  {code: 'hi', name: 'Hindi', native: 'हिन्दी', available: true}, {code: 'kn', name: 'Kannada', native: 'ಕನ್ನಡ', available: true}];
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
  return <form className="create-form" onSubmit={submit} noValidate>
    <div className="section-heading"><div><span className="eyebrow">START WITH A QUESTION</span><h2>What are we learning today?</h2></div><span className="form-number">01</span></div>
    <label htmlFor="topic">Your topic</label><textarea id="topic" name="topic" rows={2} maxLength={120} placeholder="How does a Python loop work?"
      aria-describedby="topic-help topic-error" aria-invalid={Boolean(error)} value={input.topic}
      onKeyDown={(event) => {if (event.key === 'Enter' && !event.shiftKey) {event.preventDefault(); event.currentTarget.form?.requestSubmit();}}}
      onChange={(event) => {setInput({...input, topic: event.target.value}); setError('');}} onBlur={() => {if (input.topic) setError(validate());}} />
    <div className="field-help"><span id="topic-help">A small question can unlock a big idea.</span><span>{input.topic.length}/120</span></div>
    {error && <p id="topic-error" role="alert" className="field-error">{error}</p>}
    <div className="example-chips">{['Python loops', "Ohm’s law", 'Photosynthesis'].map((topic) => <button key={topic} type="button" onClick={() => {setInput({...input, topic}); setError('');}}>{topic} →</button>)}</div>
    <div className="form-grid"><label>Difficulty<select aria-label="Difficulty" value={input.level} onChange={(event) => setInput({...input, level: event.target.value as Level})}>
      {(config?.levels ?? ['beginner', 'intermediate']).map((level) => <option key={level} value={level}>{level[0]?.toUpperCase()}{level.slice(1)}</option>)}</select></label>
      <label>Language<select aria-label="Language" value={input.language} onChange={(event) => setInput({...input, language: event.target.value as Language})}>
        {(config?.languages ?? coreLanguages).map((language) => <option key={language.code} value={language.code} disabled={!language.available} title={language.available ? '' : 'Not available on this backend'}>
          {language.name} · {language.native}{'tier' in language && language.tier === 'bonus' ? ' (beta)' : ''}{language.available ? '' : ' — unavailable'}</option>)}</select></label></div>
    <label className="duration-label" htmlFor="duration">Lesson length <strong>{input.target_seconds} seconds</strong></label>
    <input id="duration" type="range" min={config?.target_seconds.min ?? 30} max={config?.target_seconds.max ?? 90} step={config?.target_seconds.step ?? 15}
      value={input.target_seconds} onChange={(event) => setInput({...input, target_seconds: Number(event.target.value)})} />
    <div className="range-labels"><span>{config?.target_seconds.min ?? 30}s · A quick insight</span><span>{config?.target_seconds.max ?? 90}s · A closer look</span></div>
    <div className="form-grid"><label>Narration voice<select aria-label="Narration voice" value={input.voice} onChange={(event) => setInput({...input, voice: event.target.value as Voice})}>
      {(config?.voices ?? ['female', 'male']).map((voice) => <option key={voice} value={voice}>{voice === 'female' ? 'Female' : 'Male'}</option>)}</select></label>
      <label>Speech speed<select aria-label="Speech speed" value={input.speed} onChange={(event) => setInput({...input, speed: Number(event.target.value)})}>
        {(config?.speeds ?? [0.85, 1, 1.15]).map((speed) => <option key={speed} value={speed}>{speed}×{speed === 1 ? ' · Natural' : speed < 1 ? ' · Slower' : ' · Faster'}</option>)}</select></label></div>
    <button className="button primary generate" type="submit" disabled={!health?.ok || !config || busy}>{busy ? 'Submitting…' : 'Generate animated lesson'} <span>→</span></button>
    <p className="form-footnote">{health?.ok && config ? 'Generated locally. Your curiosity stays on this machine.' : 'Live generation needs the local backend. Explore a sample alongside.'}</p>
  </form>;
}
