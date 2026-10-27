import type {Job, StageName} from './api';

const names: Record<StageName, string> = {plan: 'Planning', validate: 'Checking', translate: 'Translating',
  voice: 'Voicing', timeline: 'Syncing', export: 'Making MP4'};
const symbols = {pending: '○', running: '◉', done: '✓', cached: '↻', skipped: '−', error: '×'};
export function Progress({job, compact = false}: {job: Job | null; compact?: boolean}) {
  return <section className={`progress-card ${compact ? 'compact' : ''}`} aria-label="Generation progress">
    <div className="section-heading"><div><span className="eyebrow">YOUR LESSON, IN THE MAKING</span>
      <h2>{job?.status === 'done' ? 'Ready to explore.' : job?.status === 'error' ? 'Something needs attention.' : 'Turning your question into a lesson.'}</h2></div>
      {job && <span className="tag">{(job.total_ms / 1000).toFixed(1)} s · {job.device_profile.toUpperCase()}</span>}</div>
    {job?.status === 'queued' && <p>Waiting in the local queue · position {job.queue_position}</p>}
    <ol className="stages">{(job?.stages ?? (Object.keys(names) as StageName[]).map((name) =>
      ({name, status: 'pending' as const, ms: null, note: '', rss_mb: null}))).map((stage) =>
      <li key={stage.name} data-status={stage.status}><span className="stage-icon" aria-hidden="true">{symbols[stage.status]}</span>
        <div><strong>{names[stage.name]}</strong><small>{stage.status}{stage.note ? ` · ${stage.note}` : ''}</small></div>
        <span>{stage.ms === null ? '—' : `${(stage.ms / 1000).toFixed(1)} s`}</span></li>)}</ol>
    {job?.stages.some((stage) => stage.name === 'export' && stage.status === 'running') &&
      <div><progress value={job.progress} max={1} aria-label="MP4 export progress" /><small>Making MP4 · {Math.round(job.progress * 100)}%</small></div>}
  </section>;
}
