import {useEffect, useState} from 'react';
import {fetchLibrary, mergeLibrary, readHistory, type LessonCategory} from './library';
import {samples} from './samples';

const filters = ['All', 'Programming', 'Science', 'Mathematics'] as const;
const languageNames: Record<string, string> = {en: 'English', hi: 'हिन्दी', kn: 'ಕನ್ನಡ', ta: 'தமிழ்', te: 'తెలుగు', bn: 'বাংলা', mr: 'मराठी'};
const symbols: Record<LessonCategory, string> = {Programming: '</>', Science: '◎', Mathematics: 'ƒ(x)', Other: '✧'};

export function Library() {
  const [history] = useState(readHistory);
  const [lessons, setLessons] = useState(history.lessons);
  const [loading, setLoading] = useState(true);
  const [localOnly, setLocalOnly] = useState(false);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<typeof filters[number]>('All');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    void fetchLibrary(controller.signal).then((remote) => {
      if (!controller.signal.aborted) {setLessons(mergeLibrary(remote, readHistory().lessons)); setLocalOnly(false);}
    }).catch(() => {
      if (!controller.signal.aborted) {setLessons(readHistory().lessons); setLocalOnly(true);}
    }).finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [retry]);
  const visible = lessons.filter((lesson) => (filter === 'All' || lesson.category === filter) &&
    `${lesson.title} ${lesson.language} ${languageNames[lesson.language] ?? ''}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  return <section className="library-page" aria-labelledby="library-title">
    <div className="library-heading"><div><span className="eyebrow">A LITTLE KNOWLEDGE, ALWAYS WITH YOU</span>
      <h1 id="library-title">Your Lessons</h1><p className="muted">Come back to a concept. Pick up where curiosity left you.</p></div>
      <a className="button primary" href="#/">+ Create Lesson</a></div>
    <div className="library-toolbar"><label className="library-search"><span aria-hidden="true">⌕</span><input type="search" aria-label="Search lessons" placeholder="Search your lessons…" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      <div className="library-filters" aria-label="Filter lessons">{filters.map((item) => <button key={item} aria-pressed={filter === item} className={filter === item ? 'selected' : ''} onClick={() => setFilter(item)}>{item}</button>)}</div></div>
    <p className="library-storage-note muted">{loading ? 'Checking your local lesson library…' : localOnly ? 'Showing lessons opened in this browser. Connect your local backend to load its full library.' : 'Lessons from your local backend and this browser’s history.'}
      {!history.persistent && ' Browser storage is unavailable; history lasts for this session.'}
      {localOnly && !loading && <> <button className="text-button" onClick={() => setRetry((value) => value + 1)}>Refresh library</button></>}</p>
    {lessons.length === 0 ? <div className="library-empty empty-state"><div className="empty-illustration" aria-hidden="true"><span>▤</span><span>✧</span></div>
      <h2>No lessons yet</h2><p>Create your first visual lesson and turn a difficult concept into something easy to understand.</p><a className="button primary" href="#/">Create Lesson →</a></div> : visible.length === 0 ?
      <div className="library-empty empty-state"><h2>No matching lessons</h2><p>Try another topic or view all your lessons.</p><button onClick={() => {setQuery(''); setFilter('All');}}>Clear filters</button></div> :
      <div className="library-grid">{visible.map((lesson) => {
        const href = `#/lesson/${encodeURIComponent(lesson.id)}?variant=${encodeURIComponent(lesson.variant)}`;
        const date = lesson.createdAt ?? lesson.openedAt;
        return <article className={`library-card library-${lesson.category.toLowerCase()}`} key={`${lesson.id}-${lesson.variant}`}>
          <a href={href} className="library-thumbnail" aria-label={`Play ${lesson.title}`}><span aria-hidden="true">{symbols[lesson.category]}</span><span className="thumbnail-play" aria-hidden="true">▶</span></a>
          <div className="library-card-copy"><div className="library-card-meta"><span className="eyebrow">{lesson.category}</span><span className={`tag ${lesson.mp4 ? 'complete-tag' : ''}`}>{lesson.mp4 ? 'Video ready' : 'Playable'}</span></div>
            <h2><a href={href}>{lesson.title}</a></h2><p className="muted">{Math.round(lesson.seconds)} sec · <span lang={lesson.language}>{languageNames[lesson.language] ?? lesson.language}</span>{lesson.scenes !== null ? ` · ${lesson.scenes} scenes` : ''}</p>
            {date && <small className="muted">{lesson.createdAt ? 'Created' : 'Last opened'} <time dateTime={date}>{new Date(date).toLocaleDateString(undefined, {month: 'short', day: 'numeric', year: 'numeric'})}</time></small>}
            <div className="library-card-actions"><a href={href} className="button secondary">▶ Play lesson</a>{lesson.mp4 ? <a href={`${lesson.mp4}${lesson.mp4.includes('?') ? '&' : '?'}download=1`} download className="library-download" aria-label={`Download ${lesson.title} MP4`}>↓ MP4</a> : <span className="muted">MP4 not ready</span>}</div>
          </div></article>;
      })}</div>}
    <section className="library-samples" aria-labelledby="library-samples-title"><div className="section-heading"><div><span className="eyebrow">A GOOD PLACE TO START</span><h2 id="library-samples-title">Explore a sample lesson</h2></div><span className="tag">3 SAMPLES</span></div>
      <p className="muted">Hand-written examples with silent preview playback. No generation needed.</p>
      <div className="library-grid">{samples.map((sample) => <a key={sample.id} className={`library-sample sample-${sample.id}`} href={`#/sample/${sample.id}`}>
        <span className="sample-mini-art" aria-hidden="true">{sample.symbol}</span><div><span className="eyebrow">{sample.subject}</span><h3>{sample.props.lesson.title}</h3><p className="muted">{Math.round(sample.props.timeline.duration_frames / sample.props.timeline.fps)} sec · {languageNames[sample.props.lesson.language] ?? sample.props.lesson.language} · Sample</p><span className="sample-link">Play sample →</span></div></a>)}</div>
    </section>
  </section>;
}
