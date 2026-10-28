import {useEffect, useState, type FormEvent} from 'react';
import type {AppConfig, CreateLessonRequest, Health, Level, Subject, Voice} from './api';
import type {Language} from '../lesson/types';
import {voicesFor} from './api';

const defaultInput: CreateLessonRequest = {topic: '', level: 'beginner', language: 'en', target_seconds: 60, voice: 'female', speed: 1};
const coreLanguages = [{code: 'en', name: 'English', native: 'English', available: true},
  {code: 'hi', name: 'Hindi', native: 'हिन्दी', available: false}, {code: 'kn', name: 'Kannada', native: 'ಕನ್ನಡ', available: false}];
const examples = ['Python loop', 'Water Cycle', 'Binary Search'];
const capitalize = (text: string) => `${text[0]?.toUpperCase()}${text.slice(1)}`;
let rememberedInput = defaultInput;
let initializedFromConfig = false;

export function CreateForm({config, health, busy, fieldErrors, onClearErrors, onSubmit}: {
  config: AppConfig | null; health: Health | null; busy: boolean; fieldErrors: Record<string, string>;
  onClearErrors: () => void; onSubmit: (input: CreateLessonRequest) => void;
}) {
  const [input, setInput] = useState(rememberedInput);
  const [error, setError] = useState('');
  const languages = coreLanguages.map((language) => ({...language,
    available: config?.languages.some((option) => option.code === language.code && option.available) ?? false}));
  const languageAvailable = languages.some((language) => language.code === input.language && language.available);
  const voiceOptions = voicesFor(config, input.language);
  const voiceAvailable = voiceOptions.some((option) => option.voice === input.voice);
  useEffect(() => {
    if (voiceOptions.length && !voiceAvailable) setInput((previous) => ({...previous, voice: voiceOptions[0]!.voice}));
  }, [config, input.language, voiceAvailable]);
  useEffect(() => {rememberedInput = input;}, [input]);
  useEffect(() => { if (config && !initializedFromConfig) {
    initializedFromConfig = true;
    setInput((previous) => ({...previous, ...config.defaults, language: 'en', target_seconds: config.target_seconds.default}));
  } }, [config]);
  const validate = () => input.topic.trim().length < 3 ? 'Type a topic first (at least 3 characters).' : input.topic.trim().length > 120 ? 'Keep your topic to 120 characters.' : '';
  const submit = (event: FormEvent) => {
    event.preventDefault(); const message = validate(); setError(message);
    if (message) {document.getElementById('topic')?.focus(); return;}
    if (!health?.models.planner.ready || !config || busy) return;
    if (!languageAvailable) {setError('Choose a language enabled by the backend.'); return;}
    if (!voiceAvailable) {setError('Choose an available voice for this language.'); return;}
    onSubmit({...input, topic: input.topic.trim()});
  };
  const duration = config?.target_seconds ?? {min: 30, max: 90, step: 15, default: 60};
  const durations = Array.from({length: Math.floor((duration.max - duration.min) / duration.step) + 1}, (_, i) => duration.min + i * duration.step);
  return <form className="create-form" onSubmit={submit} noValidate aria-label="Create your lesson" aria-busy={busy}>
    <div className="section-heading"><div><span className="eyebrow">A LITTLE CURIOSITY GOES A LONG WAY</span><h2>Create your lesson</h2></div>
      <span className="form-title-icon" aria-hidden="true">✧</span></div>
    <label htmlFor="topic">What would you like to understand?</label>
    <div className="topic-field"><span className="topic-sparkle" aria-hidden="true">✧</span>
      <textarea id="topic" name="topic" className="resize-none" rows={3} maxLength={120} placeholder="e.g. Explain how a Python for loop works"
        aria-describedby={`topic-help${error || fieldErrors.topic ? ' topic-error' : ''}`} aria-invalid={Boolean(error || fieldErrors.topic)} value={input.topic}
        onKeyDown={(event) => {if (event.key === 'Enter' && !event.shiftKey) {event.preventDefault(); event.currentTarget.form?.requestSubmit();}}}
        onChange={(event) => {setInput({...input, topic: event.target.value}); setError(''); onClearErrors();}} onBlur={() => {if (input.topic) setError(validate());}} />
    </div>
    <div className="field-help"><span id="topic-help">Start with a question, a topic, or a big idea.</span><span>{input.topic.length}/120</span></div>
    {(error || fieldErrors.topic) && <p id="topic-error" role="alert" className="field-error">{error || fieldErrors.topic}</p>}
    <div className="example-chips" aria-label="Example topics">{examples.map((topic) => <button key={topic} type="button" onClick={() => {setInput({...input, topic}); setError(''); onClearErrors();}}>{topic}</button>)}</div>
    <div className="form-grid">
      <fieldset className="setting-group"><legend>Difficulty</legend><div className="segmented-control">
        {(config?.levels ?? ['beginner', 'intermediate']).map((level) => <label className={`segment-option ${input.level === level ? 'is-selected' : ''}`} key={level}>
          <input type="radio" name="level" value={level} checked={input.level === level} onChange={() => setInput({...input, level: level as Level})} /><span>{capitalize(level)}</span>
        </label>)}</div></fieldset>
      <fieldset className="setting-group"><legend>Language</legend><div className="segmented-control language-options">
        {languages.map((language) => <label className={`segment-option ${input.language === language.code ? 'is-selected' : ''}`} key={language.code}
          title={language.available ? language.name : config ? 'Not enabled by the backend' : 'Waiting for backend configuration'}>
          <input type="radio" name="language" value={language.code} checked={input.language === language.code} disabled={!language.available}
            onChange={() => setInput({...input, language: language.code as Language})} /><span lang={language.code}>{language.native}</span>
        </label>)}</div></fieldset>
      <fieldset className="setting-group duration-group"><legend>Lesson duration <span className="setting-hint">A little time. A clearer picture.</span></legend>
        <div className="segmented-control duration-options">{durations.map((seconds) => <label className={`segment-option ${input.target_seconds === seconds ? 'is-selected' : ''}`} key={seconds}>
          <input type="radio" name="target_seconds" value={seconds} checked={input.target_seconds === seconds} onChange={() => setInput({...input, target_seconds: seconds})} /><span>{seconds} sec</span>
        </label>)}</div></fieldset>
      <fieldset className="setting-group"><legend>Narration voice</legend>{input.language === 'kn' && <p className="setting-hint">Approved Kannada voice: Suresh, seed 21. Female Anu is not approved.</p>}<div className="segmented-control voice-options">
        {(config?.voices ?? ['female', 'male']).map((voice) => <label className={`segment-option ${input.voice === voice ? 'is-selected' : ''}`} key={voice}>
          <input type="radio" name="voice" value={voice} checked={input.voice === voice} disabled={!voiceOptions.some((option) => option.voice === voice)} onChange={() => setInput({...input, voice: voice as Voice})} /><span>{capitalize(voice)}{input.language === 'kn' && voice === 'male' ? ' · Suresh (seed 21)' : ''}</span>
        </label>)}</div></fieldset>
    </div>
    <details className="advanced-settings"><summary>More options</summary><div className="advanced-grid"><label>Subject<select aria-label="Subject" value={input.subject ?? ''} onChange={(event) => setInput((previous) => {
      if (event.target.value) return {...previous, subject: event.target.value as Subject};
      const withoutSubject = {...previous}; delete withoutSubject.subject; return withoutSubject;
    })}><option value="">Choose automatically</option>
      <option value="programming">Programming</option><option value="science">Science</option><option value="other">Other</option></select></label>
      <label>Speech speed<select aria-label="Speech speed" value={input.speed} onChange={(event) => setInput({...input, speed: Number(event.target.value)})}>
      {(config?.speeds ?? [0.85, 1, 1.15]).map((speed) => <option key={speed} value={speed}>{speed}×{speed === 1 ? ' · Natural' : speed < 1 ? ' · Slower' : ' · Faster'}</option>)}</select></label></div></details>
    {Object.entries(fieldErrors).filter(([field]) => field !== 'topic').map(([field, message]) =>
      <p key={field} role="alert" className="field-error">{capitalize(field.replaceAll('_', ' '))}: {message}</p>)}
    <button className="button primary generate" type="submit" disabled={!health?.models.planner.ready || !config || !languageAvailable || !voiceAvailable || busy} aria-describedby="generation-help"
      title={!health?.models.planner.ready ? 'Start Ollama and make the planner model available' : busy ? 'Submitting your lesson' : 'Generate this lesson locally'}>
      <span aria-hidden="true">✧</span> {busy ? 'Submitting…' : 'Generate Visual Lesson'} <span aria-hidden="true">→</span></button>
    <p className="privacy-note"><span aria-hidden="true">⌑</span> Runs locally · Your lesson stays private</p>
    <p id="generation-help" className="form-footnote backend-hint">{health?.models.planner.ready ? 'Planner ready. Voice loads automatically on first use.' : 'Connect Ollama and the planner model to generate. Sample lessons remain available.'}</p>
  </form>;
}
