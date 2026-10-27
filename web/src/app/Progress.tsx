import type {Job, StageName} from './api';

const names: Record<StageName, string> = {plan: 'Understanding your topic', validate: 'Checking lesson structure', translate: 'Preparing your language',
  voice: 'Generating narration', timeline: 'Synchronizing animation', export: 'Preparing your video'};
const symbols = {pending: '○', running: '◉', done: '✓', cached: '✓', skipped: '−', error: '!'};
const statusLabels = {pending: 'Up next', running: 'In progress', done: 'Complete', cached: 'Ready from cache', skipped: 'Not needed', error: 'Needs attention'};

export function Progress({job, compact = false}: {job: Job | null; compact?: boolean}) {
  const stages = job?.stages ?? (Object.keys(names) as StageName[]).map((name) =>
    ({name, status: 'pending' as const, ms: null, note: '', rss_mb: null}));
  const finished = stages.filter((stage) => ['done', 'cached', 'skipped'].includes(stage.status)).length;
  const exporting = stages.some((stage) => stage.name === 'export' && stage.status === 'running');
  const failed = job?.status === 'error';
  return <section className={`progress-card ${compact ? 'compact' : ''}`} aria-label="Generation progress">
    {!compact && <div className={`generation-illustration ${failed ? 'is-error' : job?.status === 'done' ? 'is-done' : 'is-working'}`} aria-hidden="true">
      <span className="generation-orbit" /><span className="generation-book">{failed ? '!' : job?.status === 'done' ? '✓' : '✧'}</span>
      <span className="generation-spark one">+</span><span className="generation-spark two">✦</span></div>}
    <div className="section-heading"><div><span className="eyebrow">ONE IDEA. A WHOLE NEW WAY TO SEE IT.</span>
      <h2>{job?.status === 'done' ? 'Your lesson is ready' : failed ? 'We couldn’t finish this lesson.' : 'Creating your visual lesson'}</h2></div>
      {job && <span className="tag">{(job.total_ms / 1000).toFixed(1)} s elapsed</span>}</div>
    <p className="generation-summary" role="status">{failed ? 'The local AI pipeline encountered an issue. You can try creating the lesson again or explore a sample.' :
      job?.status === 'done' ? 'Your explanation is ready to watch, revisit, and download.' :
      job?.status === 'queued' ? `Waiting in the local queue · position ${job.queue_position}` : 'A clear explanation is coming together, one step at a time.'}</p>
    <ol className="stages">{stages.map((stage) =>
      <li key={stage.name} data-status={stage.status} aria-current={stage.status === 'running' ? 'step' : undefined}><span className="stage-icon" aria-hidden="true">{symbols[stage.status]}</span>
        <div><strong>{names[stage.name]}</strong><small>{statusLabels[stage.status]}</small></div>
        <span>{stage.ms === null ? '' : `${(stage.ms / 1000).toFixed(1)} s`}</span></li>)}</ol>
    <div className="pipeline-progress"><div className="pipeline-progress-label"><span>{exporting ? 'Rendering MP4' : 'Lesson preparation'}</span>
      <strong>{exporting ? `${Math.round((job?.progress ?? 0) * 100)}%` : `${finished} of ${stages.length} stages complete`}</strong></div>
      <progress value={exporting ? job?.progress ?? 0 : finished} max={exporting ? 1 : stages.length} aria-label={exporting ? 'MP4 export progress' : 'Completed generation stages'} /></div>
    {failed ? <div className="generation-error-actions"><a className="button primary" href="#/">Try Again</a><a className="button secondary" href="#/sample/python">Use Sample Lesson</a></div> :
      <div className="progress-tip"><span aria-hidden="true">◷</span><p>Your lesson becomes playable before the final MP4 finishes rendering.</p></div>}
  </section>;
}
