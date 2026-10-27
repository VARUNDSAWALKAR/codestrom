import {useEffect, useRef, useState} from 'react';
import type {RenderProps} from '../lesson/types';
import {createLesson, getConfig, getHealth, getLesson, wait,
  type AppConfig, type CreateLessonRequest, type Health, type LessonResponse} from './api';
import {CreateForm} from './CreateForm';
import {LessonPlayer} from './LessonPlayer';
import {Progress} from './Progress';
import {samples} from './samples';
import {useJob} from './useJob';
import './styles.css';

function readRoute() {
  const [pathname = '/', query = ''] = location.hash.slice(1).split('?');
  const parts = pathname.split('/');
  const parameters = new URLSearchParams(query);
  let id = parts[2] ?? '';
  try { id = decodeURIComponent(id); } catch { id = ''; }
  return {kind: parts[1] ?? '', id, variant: parameters.get('variant') ?? undefined,
    jobId: parts[1] === 'job' ? parts[2] : parameters.get('job') ?? undefined};
}

export function App() {
  const [route, setRoute] = useState(readRoute);
  const [health, setHealth] = useState<Health | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [connectionError, setConnectionError] = useState('');
  const [configError, setConfigError] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<LessonResponse | null>(null);
  const [retry, setRetry] = useState(0);
  const [connectionRetry, setConnectionRetry] = useState(0);
  const submission = useRef<AbortController | null>(null);
  const submissionLock = useRef(false);
  const status = useJob(route.jobId, retry);
  const sample = route.kind === 'sample' ? samples.find((item) => item.id === route.id) : undefined;
  useEffect(() => {
    const update = () => {setRoute(readRoute()); setError(''); submission.current?.abort(); submissionLock.current = false; setBusy(false);};
    window.addEventListener('hashchange', update);
    return () => {window.removeEventListener('hashchange', update); submission.current?.abort();};
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void getConfig(controller.signal).then((value) => {
      if (!controller.signal.aborted) {setConfig(value); setConfigError('');}
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) {setConfig(null); setConfigError(reason instanceof Error ? reason.message : 'Could not load backend settings.');}
    });
    void (async () => {
      while (!controller.signal.aborted) {
        try {
          const result = await getHealth(controller.signal);
          if (controller.signal.aborted) return;
          setHealth(result); setConnectionError('');
        } catch (reason) {
          if (controller.signal.aborted) return;
          setHealth(null); setConnectionError(reason instanceof Error ? reason.message : 'Backend unavailable.');
        }
        await wait(10000, controller.signal);
      }
    })().catch(() => {});
    return () => controller.abort();
  }, [connectionRetry]);
  useEffect(() => {
    setResponse(null); setLoading(false);
    if (route.kind !== 'lesson' || route.jobId) return;
    const controller = new AbortController(); setLoading(true);
    void getLesson(route.id, route.variant, controller.signal).then((lesson) => {
      if (!controller.signal.aborted) setResponse(lesson);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not load lesson.');
    }).finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [route.id, route.kind, route.variant, route.jobId, retry]);
  useEffect(() => {
    if (status.lesson && route.kind === 'job') location.hash = `/lesson/${encodeURIComponent(status.lesson.lesson_id)}?variant=${encodeURIComponent(status.lesson.variant)}&job=${encodeURIComponent(route.jobId ?? '')}`;
  }, [status.lesson, route.kind, route.jobId]);
  const submit = async (input: CreateLessonRequest) => {
    if (submissionLock.current) return;
    submissionLock.current = true;
    const controller = new AbortController(); submission.current = controller;
    setBusy(true); setError('');
    try {
      const created = await createLesson(input, controller.signal);
      if (!controller.signal.aborted) location.hash = `/job/${encodeURIComponent(created.job_id)}`;
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not submit lesson.');
    } finally {
      submissionLock.current = false;
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  const live = status.lesson ?? response;
  const props: RenderProps | null = sample?.props ?? (live ? {lesson: live.lesson, timeline: live.timeline,
    mediaBase: '', audioVariant: 'web', showCaptions: true} : null);
  const home = route.kind === '';
  const unknown = (!home && !['sample', 'lesson', 'job'].includes(route.kind)) || (route.kind === 'sample' && !sample);
  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={(event) => {event.preventDefault(); document.getElementById('main-content')?.focus();}}>Skip to content</a>
    <header className="site-header"><a href="#/" className="brand" aria-label="Blu VisualTeacher home"><span className="brand-icon">b<span>·</span></span>
      <span>blu<span className="brand-sub">VisualTeacher</span></span></a>
      <nav aria-label="Main navigation"><a href="#/">Create a lesson</a><a href="#/sample/python">Explore a sample <span>→</span></a></nav>
      <span className="local-badge"><span /> Built for local learning</span></header>
    <main id="main-content" tabIndex={-1}>
      {home ? <>
        <section className="hero"><div className="eyebrow"><span className="small-star">✧</span> LESS READING. MORE UNDERSTANDING.</div>
          <h1>Make the <span>“why”</span> click.</h1><p>Turn a question into a short, animated lesson.<br />See it unfold. Hear it in your language. Learn at your pace.</p>
          <div className="hero-features"><span>→ Visual, step by step</span><span>अ English · हिन्दी · ಕನ್ನಡ</span><span>◎ Runs locally</span></div></section>
        <div className="workspace"><CreateForm config={config} health={health} busy={busy} onSubmit={(input) => {void submit(input);}} />
          <aside className="samples-panel"><div className="section-heading"><div><span className="eyebrow">A LITTLE INSPIRATION</span><h2>See an idea come to life.</h2></div><span className="tag">3 SAMPLES</span></div>
            <p className="muted">No setup needed. Explore these hand-written lessons.</p>
            <div className="sample-cards">{samples.map((item, index) => <a className={`sample-card sample-${item.id}`} key={item.id} href={`#/sample/${item.id}`}>
              <div className="sample-art" aria-hidden="true"><span className="art-symbol">{item.symbol}</span><span className="art-dot one" /><span className="art-dot two" /><span className="art-line" /></div>
              <div className="sample-copy"><span className="eyebrow">{item.subject} <span>0{index + 1}</span></span><h3>{item.name}</h3><p>{item.detail}</p>
                <span className="sample-link">Explore lesson <span>→</span></span></div></a>)}</div>
            <div className="sample-note"><span>✧</span><p>Start with curiosity.<br /><strong>Leave with a clearer picture.</strong></p></div></aside></div>
      </> : <><a className="back-link" href="#/">← Create another lesson</a>
        <div className="lesson-heading"><div><span className="eyebrow">{sample ? 'THE SAMPLE COLLECTION' : 'YOUR LEARNING SPACE'}</span>
          <h1>{props?.lesson.title ?? (loading ? 'Opening your lesson…' : 'One idea, coming together.')}</h1></div>
          {sample && <span className="tag">HAND-WRITTEN · NOT AI-GENERATED</span>}</div>
        {sample && <div className="notice">Sample preview · estimated timing · no narration audio. Live lessons use audio-derived timing.</div>}
        {status.job?.fallback && <div className="notice warning" role="status">{status.job.fallback_reason} Playing our sample lesson instead.</div>}
        {loading && <div className="empty-state" role="status">Loading the lesson from the local backend…</div>}
        {props && <LessonPlayer key={`${props.lesson.lesson_id}-${props.timeline.variant}-${Boolean(sample)}`} props={props} preview={Boolean(sample)} response={sample ? null : live} job={sample ? null : status.job} />}
        {!sample && route.jobId && <Progress job={status.job} compact={Boolean(props)} />}
        {unknown && <div role="alert" className="notice error">This page does not exist. <a href="#/">Return to the lesson creator.</a></div>}
      </>}
      {(error || status.error) && <div role="alert" className="notice error">{error || status.error}<div className="error-actions">
        <button onClick={() => {setError(''); setRetry((value) => value + 1);}}>Retry connection</button><a href="#/sample/python">Play the sample lesson</a></div></div>}
      <section className="backend-status" aria-label="Backend status"><div><span className={`status-dot ${health?.ok ? 'ready' : ''}`} />
        <strong>{health?.ok ? 'Local backend ready' : health ? 'Local models are warming up' : connectionError ? 'Local backend unavailable' : 'Checking local backend…'}</strong>
        <span>{health ? `${health.device_profile.toUpperCase()} · ${health.offline ? 'Offline mode' : 'Offline mode not confirmed'}` : 'Sample lessons are always available'}</span></div>
        <div className="health-chips">{health && <><span>Planner {health.models.planner.ready ? '✓' : '○'}</span><span>Translator {health.models.translator.ready ? '✓' : '○'}</span><span>Voice {health.models.tts_kokoro.ready ? '✓' : '○'}</span><span>Renderer {health.renderer.bundle_ready ? '✓' : '○'}</span></>}
          <button onClick={() => setConnectionRetry((value) => value + 1)}>Refresh status</button></div>
        {(configError || connectionError) && <p className="muted">{configError || connectionError}</p>}
      </section>
    </main>
    <footer><a href="#/" className="footer-brand">blu VisualTeacher</a><span>Big ideas. Clear pictures. Your pace.</span><span>Made for curious minds →</span></footer>
  </div>;
}
