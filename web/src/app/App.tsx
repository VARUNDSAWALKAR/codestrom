import {useEffect, useRef, useState} from 'react';
import type {RenderProps} from '../lesson/types';
import {ApiError, createLesson, getConfig, getHealth, getLesson, wait,
  type AppConfig, type CreateLessonRequest, type Health, type LessonResponse} from './api';
import {CreateForm} from './CreateForm';
import {LessonPlayer} from './LessonPlayer';
import {Progress} from './Progress';
import {samples} from './samples';
import {useJob} from './useJob';
import {VisualPreview} from './VisualPreview';
import {About} from './About';
import './styles.css';

function readRoute() {
  const [pathname = '/', query = ''] = location.hash.slice(1).split('?');
  const parts = pathname.split('/');
  const parameters = new URLSearchParams(query);
  let id = parts[2] ?? '';
  try { id = decodeURIComponent(id); } catch { id = ''; }
  return {kind: parts[1] ?? '', id, variant: parameters.get('variant') ?? undefined,
    jobId: parts[1] === 'job' ? id : parameters.get('job') ?? undefined};
}

export function App() {
  const [route, setRoute] = useState(readRoute);
  const [health, setHealth] = useState<Health | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [connectionError, setConnectionError] = useState('');
  const [configError, setConfigError] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
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
    setBusy(true); setError(''); setFieldErrors({});
    try {
      const created = await createLesson(input, controller.signal);
      if (!controller.signal.aborted) location.hash = `/job/${encodeURIComponent(created.job_id)}`;
    } catch (reason) {
      if (!controller.signal.aborted) {
        if (reason instanceof ApiError && reason.status === 422) {
          setFieldErrors(Object.fromEntries(reason.fields.map((item) => [item.field, item.message])));
        }
        setError(reason instanceof Error ? reason.message : 'Could not submit lesson.');
      }
    } finally {
      submissionLock.current = false;
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  const live = status.lesson ?? response;
  const props: RenderProps | null = sample?.props ?? (live ? {lesson: live.lesson, timeline: live.timeline,
    mediaBase: '', audioVariant: 'web', showCaptions: true} : null);
  const home = route.kind === '';
  const aiStatus = health?.models.planner.ready && health.offline ? 'ready' : health ? 'starting' : 'disconnected';
  const aiStatusLabel = aiStatus === 'ready' ? 'Ready' : aiStatus === 'starting' ? 'Starting' : 'Not connected';
  const unknown = (!home && !['sample', 'lesson', 'job', 'about'].includes(route.kind)) || (route.kind === 'sample' && !sample);
  const mockMode = health?.mock === true || health?.mock_pipeline === true || config?.mock === true || status.job?.mock === true || live?.mock === true;
  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={(event) => {event.preventDefault(); document.getElementById('main-content')?.focus();}}>Skip to content</a>
    {mockMode && <div className="mock-banner" role="status"><strong>MOCK MODE</strong><span>Fixture data is active. Outputs are for integration testing.</span></div>}
    <header className="site-header"><a href="#/" className="brand" aria-label="Blu VisualTeacher home"><span className="brand-icon">b<span>·</span></span>
      <span>blu<span className="brand-sub">VisualTeacher</span></span></a>
      <nav aria-label="Main navigation"><a href="#/" aria-current={home ? 'page' : undefined}>Create Lesson</a><a href="#/about" aria-current={route.kind === 'about' ? 'page' : undefined}>About</a></nav>
      <span className={`local-badge is-${aiStatus}`} role="status" aria-label={`Offline AI: ${aiStatusLabel}`}
        title={aiStatus === 'ready' ? 'Local AI is ready and offline mode is enabled' : aiStatus === 'starting' ? 'The local backend is connected and its models are starting' : 'Sample lessons are available; the local AI backend is not connected'}>
        <span aria-hidden="true" /> Offline AI <span className="badge-detail">{aiStatusLabel}</span></span></header>
    <main id="main-content" tabIndex={-1}>
      {home ? <>
        <section className="hero"><div className="hero-copy"><div className="hero-pill"><span>✦</span> YOUR LOCAL LEARNING STUDIO</div>
          <h1>Turn any concept into<br />a <span>visual lesson.</span></h1><p>Describe what you want to understand. Blu maps the idea into a short, narrated animation you can watch, revisit, and keep.</p>
          <div className="hero-actions"><a className="button primary" href="#lesson-creator">Create a lesson <span aria-hidden="true">↘</span></a><a className="hero-sample-link" href="#/sample/python"><span aria-hidden="true">▶</span> Watch a sample</a></div>
          <div className="hero-features"><span><i>✓</i> Built to make sense</span><span><i>अ</i> Multilingual-ready</span><span><i>⌂</i> Offline & private</span></div></div>
          <div className="concept-orbit" aria-hidden="true"><span className="orbit-ring ring-one" /><span className="orbit-ring ring-two" />
            <span className="orbit-node node-code">&lt;/&gt;<small>CODE</small></span><span className="orbit-node node-diagram">◇<small>DIAGRAM</small></span>
            <span className="orbit-node node-caption">CC<small>CAPTIONS</small></span><span className="orbit-core"><b>blu</b><small>IDEA ENGINE</small></span>
            <span className="orbit-caption">ONE IDEA · MANY WAYS TO SEE IT</span></div></section>
        <div className="workspace" id="lesson-creator"><CreateForm config={config} health={health} busy={busy} fieldErrors={fieldErrors}
          onClearErrors={() => {setFieldErrors({}); setError('');}} onSubmit={(input) => {void submit(input);}} />
          <VisualPreview /></div>
          <section className="experience-panel" aria-labelledby="experience-title"><div className="experience-heading"><div><span className="eyebrow">FROM QUESTION TO AHA</span>
            <h2 id="experience-title">Learning that moves with you.</h2></div><p>Every lesson turns one idea into a small journey you can see, hear, and revisit.</p></div>
            <div className="experience-grid">{[
              ['01', 'Ask anything', 'Start with a question or choose a curiosity prompt.', '✦', 'ask'],
              ['02', 'Watch it unfold', 'Follow code, diagrams, captions, and narration in sync.', '◉', 'watch'],
              ['03', 'Keep the clarity', 'Replay scenes or save the MP4 and subtitles for later.', '↗', 'keep'],
            ].map(([number, title, description, symbol, tone]) => <article className={`experience-card is-${tone}`} key={number}>
              <div className="experience-card-top"><span>{number}</span><i aria-hidden="true">{symbol}</i></div><h3>{title}</h3><p>{description}</p><span className="experience-line" aria-hidden="true" /></article>)}</div>
          </section>
          <section className="samples-panel"><div className="section-heading"><div><span className="eyebrow">CURIOSITY STARTS HERE</span><h2>Take a little knowledge break.</h2><p className="muted">Explore a sample. See what learning with Blu feels like.</p></div><a href="#/sample/python" className="text-link">Open a sample ↗</a></div>
            <div className="sample-cards">{samples.map((item, index) => <a className={`sample-card sample-${item.id}`} key={item.id} href={`#/sample/${item.id}`}>
              <div className="sample-art" aria-hidden="true"><span className="art-symbol">{item.symbol}</span><span className="art-dot one" /><span className="art-dot two" /><span className="art-line" /></div>
              <div className="sample-copy"><span className="eyebrow">{item.subject} <span>0{index + 1}</span></span><h3>{item.name}</h3><p>{item.detail}</p>
                <span className="sample-link">Explore lesson <span>→</span></span></div></a>)}</div>
            </section>
      </> : route.kind === 'about' ? <About /> : <><a className="back-link" href="#/">← Create another lesson</a>
        <div className="lesson-heading"><div><span className="eyebrow">{sample ? 'THE SAMPLE COLLECTION' : 'YOUR LEARNING SPACE'}</span>
          <h1>{props?.lesson.title ?? (loading ? 'Opening your lesson…' : 'Creating your visual lesson')}</h1></div>
          {sample && <span className="tag">HAND-WRITTEN · NOT AI-GENERATED</span>}</div>
        {sample && <div className="notice">Sample preview · estimated timing · no narration audio. Live lessons use audio-derived timing.</div>}
        {loading && <div className="lesson-skeleton" role="status"><span>Loading the lesson from the local backend…</span><i /><i /><i /></div>}
        {props && <LessonPlayer key={`${props.lesson.lesson_id}-${props.timeline.variant}-${Boolean(sample)}`} props={props} preview={Boolean(sample)} response={sample ? null : live} job={sample ? null : status.job} />}
        {!sample && route.jobId && <Progress job={status.job} compact={Boolean(props)} />}
        {unknown && <div role="alert" className="notice error">This page does not exist. <a href="#/">Return to the lesson creator.</a></div>}
      </>}
      {(error || status.error) && <div role="alert" className="notice error"><h2>We couldn’t finish this lesson.</h2><p>{error || status.error}</p><div className="error-actions">
        <button onClick={() => {setError(''); setFieldErrors({}); if (status.job?.status === 'error') location.hash = '/'; else setRetry((value) => value + 1);}}>Try Again</button></div></div>}
      <section className={`backend-status ${health ? '' : 'is-loading'}`} aria-label="Backend status"><div><span className={`status-dot ${health?.models.planner.ready ? 'ready' : ''}`} />
        <strong>{health?.models.planner.ready ? 'Local planner ready' : health ? 'Local planner is warming up' : connectionError ? 'Local backend unavailable' : 'Checking local backend…'}</strong>
        <span>{health ? `${health.device_profile.toUpperCase()} · ${health.offline ? 'Offline mode' : 'Offline mode not confirmed'}` : 'Sample lessons are always available'}</span></div>
        <div className="health-chips">{health ? <><span>Planner {health.models.planner.ready ? '✓' : '○'}</span><span className="is-muted">Translator — not connected</span><span>Voice · warms up on first use</span><span>Renderer {health.renderer.bundle_ready ? '✓' : '○'}</span></> : <><span className="skeleton-chip" /><span className="skeleton-chip" /></>}
          <button onClick={() => setConnectionRetry((value) => value + 1)}>Refresh status</button></div>
        {(configError || connectionError) && <p className="muted">{configError || connectionError}</p>}
      </section>
    </main>
    <footer><a href="#/" className="footer-brand">blu VisualTeacher</a><span>Big ideas. Clear pictures. Your pace.</span><span>Made for curious minds →</span></footer>
  </div>;
}
