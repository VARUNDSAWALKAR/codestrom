import {useEffect, useRef, useState} from 'react';
import {Player, type PlayerRef} from '@remotion/player';
import {Lesson} from '../lesson/Lesson';
import type {RenderProps} from '../lesson/types';
import {activeScene} from '../lesson/timing';
import type {Job, LessonResponse} from './api';
import {timelineSrt} from './captions';

export function LessonPlayer({props, preview, response, job}: {
  props: RenderProps; preview: boolean; response: LessonResponse | null; job: Job | null;
}) {
  const ref = useRef<PlayerRef>(null);
  const [playing, setPlaying] = useState(false);
  const [frame, setFrame] = useState(0);
  const [captions, setCaptions] = useState(true);
  const [srt, setSrt] = useState('');
  const current = activeScene(props.timeline, frame);
  const index = Math.max(0, props.timeline.scenes.findIndex((scene) => scene === current));
  const go = (offset: number) => {
    const target = props.timeline.scenes[Math.max(0, Math.min(props.timeline.scenes.length - 1, index + offset))];
    if (target) ref.current?.seekTo(target.start_frame);
  };
  const replay = () => { ref.current?.seekTo(0); ref.current?.play(); };
  useEffect(() => {
    const url = URL.createObjectURL(new Blob([timelineSrt(props.timeline)], {type: 'application/x-subrip;charset=utf-8'}));
    setSrt(url);
    return () => URL.revokeObjectURL(url);
  }, [props.timeline]);
  useEffect(() => {
    const player = ref.current;
    if (!player) return;
    const update = (event: {detail: {frame: number}}) => setFrame(event.detail.frame);
    const play = () => setPlaying(true);
    const pause = () => setPlaying(false);
    player.addEventListener('frameupdate', update); player.addEventListener('play', play);
    player.addEventListener('pause', pause); player.addEventListener('ended', pause);
    setFrame(player.getCurrentFrame()); setPlaying(player.isPlaying());
    return () => {
      player.removeEventListener('frameupdate', update); player.removeEventListener('play', play);
      player.removeEventListener('pause', pause); player.removeEventListener('ended', pause);
    };
  }, [props.lesson.lesson_id, props.timeline.variant]);
  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || (event.target instanceof HTMLElement && event.target.closest('input, textarea, select, button, a, [contenteditable]'))) return;
      if (event.code === 'Space') { event.preventDefault(); ref.current?.toggle(); }
      if (event.key === 'ArrowLeft') { event.preventDefault(); go(-1); }
      if (event.key === 'ArrowRight') { event.preventDefault(); go(1); }
      if (event.key.toLowerCase() === 'r') replay();
    };
    document.addEventListener('keydown', keyboard);
    return () => document.removeEventListener('keydown', keyboard);
  });
  const download = (url: string) => `${url}${url.includes('?') ? '&' : '?'}download=1`;
  const mp4 = response?.media.mp4;
  const exporting = job?.stages.some((stage) => stage.name === 'export' && stage.status === 'running');
  return <section className="player-card" aria-label="Lesson player">
    <div className="player-label"><span className="tag">{preview ? 'SAMPLE PREVIEW' : 'YOUR LESSON'}</span>
      <span>{props.lesson.language.toUpperCase()} · {Math.round(props.timeline.duration_frames / props.timeline.fps)} seconds{props.timeline.audio === null ? ' · Silent sample' : ''}</span></div>
    <div className="video-shell"><Player ref={ref} component={Lesson} inputProps={{...props, showCaptions: captions}}
      durationInFrames={props.timeline.duration_frames} fps={props.timeline.fps}
      compositionWidth={1280} compositionHeight={720} clickToPlay controls={false}
      style={{width: '100%', aspectRatio: '16 / 9'}}
      errorFallback={({error}) => <div role="alert" className="notice error">Could not display this lesson: {error.message}</div>} /></div>
    <div className="player-controls"><div className="transport">
      <button aria-label="Previous scene" disabled={index === 0} onClick={() => go(-1)}>←</button>
      <button className="play-button" aria-label={playing ? 'Pause' : 'Play'} onClick={() => ref.current?.toggle()}>{playing ? 'Ⅱ' : '▶'}</button>
      <button aria-label="Next scene" disabled={index === props.timeline.scenes.length - 1} onClick={() => go(1)}>→</button>
      <button aria-label="Replay lesson" onClick={replay}>↻ <span>Replay</span></button></div>
      <div className="playback-position">Scene {index + 1} / {props.timeline.scenes.length}</div>
      <button className={captions ? 'selected' : ''} aria-label="Captions" aria-pressed={captions} onClick={() => setCaptions(!captions)}>CC</button></div>
    <div className="scene-chips" aria-label="Jump to scene">{props.timeline.scenes.map((scene, n) =>
      <button key={scene.scene_id} className={index === n ? 'selected' : ''} aria-current={index === n ? 'step' : undefined}
        onClick={() => ref.current?.seekTo(scene.start_frame)}><span>{String(n + 1).padStart(2, '0')}</span>
        {props.lesson.scenes.find((item) => item.id === scene.scene_id)?.heading ?? scene.type}</button>)}</div>
    <div className="download-row"><p>{preview ? 'Hand-written sample · no AI generation or narration.' :
      `${props.lesson.source === 'fallback' ? 'Fallback lesson' : props.lesson.source === 'llm' ? 'Locally generated lesson' : props.lesson.source + ' lesson'} · ${props.lesson.model}`}</p>
      <div>{mp4 ? <a className="button secondary" href={download(mp4)} download>↓ MP4</a> :
        <button disabled title={preview ? 'Render the sample with the local export CLI.' : 'Available when the backend provides the MP4.'}>
          {exporting ? `MP4 · rendering ${Math.round((job?.progress ?? 0) * 100)}%` : 'MP4 unavailable'}</button>}
      <a className="button secondary" href={response?.media.srt ? download(response.media.srt) : srt}
        download={`${props.lesson.lesson_id}_${props.lesson.language}.srt`}>↓ SRT</a></div></div>
    <details><summary>Lesson details & warnings</summary><p>{preview ? 'Supplied sample with an estimated mock timeline.' : `Variant: ${props.timeline.variant}`}</p>
      {(response?.meta.warnings ?? props.lesson.warnings).length > 0 ? <ul>{(response?.meta.warnings ?? props.lesson.warnings).map((warning, i) => <li key={i}>{warning}</li>)}</ul> : <p>No lesson warnings.</p>}
      <details><summary>Lesson JSON</summary><pre className="json-panel">{JSON.stringify(props.lesson, null, 2)}</pre></details>
      {job && <table><caption>Measured backend stage times</caption><thead><tr><th>Stage</th><th>Seconds</th><th>Peak RAM</th></tr></thead>
        <tbody>{job.stages.map((stage) => <tr key={stage.name}><td>{stage.name}</td><td>{stage.ms === null ? '—' : (stage.ms / 1000).toFixed(2)}</td><td>{stage.rss_mb === null ? '—' : `${stage.rss_mb} MB`}</td></tr>)}</tbody></table>}
    </details>
  </section>;
}
