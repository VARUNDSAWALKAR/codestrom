import {useEffect, useRef, useState} from 'react';
import {Player, type PlayerRef} from '@remotion/player';
import {Lesson} from '../lesson/Lesson';
import type {Language, RenderProps} from '../lesson/types';
import {activeScene} from '../lesson/timing';
import type {Job, LessonResponse} from './api';
import {timelineSrt} from './captions';

const languageNames: Record<Language, string> = {en: 'English', hi: 'हिन्दी', kn: 'ಕನ್ನಡ', ta: 'தமிழ்', te: 'తెలుగు', bn: 'বাংলা', mr: 'मराठी'};
const timecode = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
function ControlIcon({name}: {name: 'play' | 'pause' | 'previous' | 'next' | 'replay' | 'volume' | 'muted' | 'download'}) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === 'play' && <path d="m9 5 11 7-11 7Z" fill="currentColor" stroke="none" />}
    {name === 'pause' && <><path d="M8 5v14M16 5v14" strokeWidth="4" /></>}
    {name === 'previous' && <><path d="M5 5v14m14-14-10 7 10 7Z" /></>}
    {name === 'next' && <><path d="M19 5v14M5 5l10 7-10 7Z" /></>}
    {name === 'replay' && <><path d="M4 5v5h5M4.5 10a8 8 0 1 1 .5 6" /></>}
    {(name === 'volume' || name === 'muted') && <><path d="m11 5-5 4H3v6h3l5 4Z" />{name === 'volume' ? <path d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14" /> : <path d="m16 9 5 6m0-6-5 6" />}</>}
    {name === 'download' && <path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" />}
  </svg>;
}

export function LessonPlayer({props, preview, response, job}: {
  props: RenderProps; preview: boolean; response: LessonResponse | null; job: Job | null;
}) {
  const ref = useRef<PlayerRef>(null);
  const [playing, setPlaying] = useState(false);
  const [frame, setFrame] = useState(0);
  const [captions, setCaptions] = useState(true);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
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
    const changeVolume = (event: {detail: {volume: number}}) => setVolume(event.detail.volume);
    const changeMute = (event: {detail: {isMuted: boolean}}) => setMuted(event.detail.isMuted);
    player.addEventListener('frameupdate', update); player.addEventListener('play', play);
    player.addEventListener('pause', pause); player.addEventListener('ended', pause);
    player.addEventListener('volumechange', changeVolume); player.addEventListener('mutechange', changeMute);
    setFrame(player.getCurrentFrame()); setPlaying(player.isPlaying());
    setVolume(player.getVolume()); setMuted(player.isMuted());
    return () => {
      player.removeEventListener('frameupdate', update); player.removeEventListener('play', play);
      player.removeEventListener('pause', pause); player.removeEventListener('ended', pause);
      player.removeEventListener('volumechange', changeVolume); player.removeEventListener('mutechange', changeMute);
    };
  }, [props.lesson.lesson_id, props.timeline.variant]);
  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || (event.target instanceof HTMLElement && event.target.closest('input, textarea, select, button, a, [contenteditable]'))) return;
      if (event.code === 'Space') { event.preventDefault(); ref.current?.toggle(); }
      if (event.key === 'ArrowLeft') { event.preventDefault(); go(-1); }
      if (event.key === 'ArrowRight') { event.preventDefault(); go(1); }
      if (event.key.toLowerCase() === 'c') setCaptions((value) => !value);
      if (event.key.toLowerCase() === 'r') replay();
    };
    document.addEventListener('keydown', keyboard);
    return () => document.removeEventListener('keydown', keyboard);
  });
  const mp4 = response?.media.mp4;
  const exportPending = job?.export_status === 'pending' || job?.export_status === 'running';
  const exportFailed = job?.export_status === 'failed' || response?.export_status === 'failed';
  const hasAudio = response ? response.media.audio_web !== null : props.timeline.audio !== null;
  const playbackTimeline = hasAudio || props.timeline.audio === null ? props.timeline : {...props.timeline, audio: null};
  const duration = props.timeline.duration_frames / props.timeline.fps;
  const language = languageNames[props.lesson.language];
  const voice = !hasAudio ? 'Silent sample' : /(^|-)female(-|$)/.test(props.timeline.variant) ? 'Female' :
    /(^|-)male(-|$)/.test(props.timeline.variant) ? 'Male' : props.timeline.voice.voice_id;
  const seek = (nextFrame: number) => {ref.current?.seekTo(nextFrame); setFrame(nextFrame);};
  return <div className="lesson-layout"><div className="player-main"><section className="player-card" aria-label="Lesson player">
    <div className="player-label"><span className="tag">{preview ? 'SAMPLE PREVIEW' : 'YOUR LESSON'}</span>
      <span>{language} · {Math.round(duration)} seconds{!hasAudio ? ' · Silent sample' : ''}</span></div>
    <div className="video-shell"><Player ref={ref} component={Lesson} inputProps={{lesson: props.lesson, timeline: playbackTimeline,
      mediaBase: '', audioVariant: 'web', showCaptions: captions}}
      durationInFrames={props.timeline.duration_frames} fps={props.timeline.fps}
      compositionWidth={1280} compositionHeight={720} clickToPlay controls={false} playbackRate={playbackRate}
      style={{width: '100%', aspectRatio: '16 / 9'}}
      errorFallback={({error}) => <div role="alert" className="notice error">Could not display this lesson: {error.message}</div>} /></div>
    <div className="seek-row"><input className="seek-slider" aria-label="Lesson timeline" type="range" min={0} max={props.timeline.duration_frames - 1} step={1}
      value={frame} aria-valuetext={`${timecode(frame / props.timeline.fps)} of ${timecode(duration)}`}
      onChange={(event) => seek(Number(event.target.value))} />
      <span className="time-display">{timecode(frame / props.timeline.fps)} <span>/ {timecode(duration)}</span></span></div>
    <div className="player-controls"><div className="transport">
      <button aria-label="Previous scene" title="Previous scene" disabled={index === 0} onClick={() => go(-1)}><ControlIcon name="previous" /></button>
      <button className="play-button" aria-label={playing ? 'Pause' : 'Play'} title="Play / Pause (Space)" onClick={() => ref.current?.toggle()}><ControlIcon name={playing ? 'pause' : 'play'} /></button>
      <button aria-label="Next scene" title="Next scene" disabled={index === props.timeline.scenes.length - 1} onClick={() => go(1)}><ControlIcon name="next" /></button>
      <button aria-label="Replay lesson" title="Replay (R)" onClick={replay}><ControlIcon name="replay" /><span>Replay</span></button></div>
      <div className="player-utilities"><div className="volume-controls" title={hasAudio ? 'Narration volume' : 'This sample has no narration audio'}>
        <button aria-label={muted ? 'Unmute narration' : 'Mute narration'} aria-pressed={muted} disabled={!hasAudio}
          onClick={() => muted ? ref.current?.unmute() : ref.current?.mute()}><ControlIcon name={muted || !hasAudio || volume === 0 ? 'muted' : 'volume'} /></button>
        <input aria-label="Narration volume" type="range" min={0} max={1} step={0.05} value={muted ? 0 : volume} disabled={!hasAudio}
          aria-valuetext={`${Math.round((muted ? 0 : volume) * 100)} percent`}
          onChange={(event) => {ref.current?.setVolume(Number(event.target.value)); ref.current?.unmute();}} /></div>
        <label className="speed-control"><span className="sr-only">Playback speed</span><select aria-label="Playback speed" value={playbackRate}
          onChange={(event) => setPlaybackRate(Number(event.target.value))}>{[0.75, 1, 1.25, 1.5].map((rate) => <option value={rate} key={rate}>{rate}×</option>)}</select></label>
        <button className={captions ? 'selected' : ''} aria-label="Captions" aria-pressed={captions} title="Toggle captions (C)" onClick={() => setCaptions(!captions)}>CC</button></div></div>
  </section>
    <div className="download-row"><div className="download-metadata"><strong>Your lesson, ready to revisit.</strong>
      <p>{Math.round(duration)} sec · {props.timeline.scenes.length} scenes · {language}</p></div>
      <div className="download-actions">{mp4 ? <a className="button primary" href={mp4} download><ControlIcon name="download" />Download MP4</a> :
        <button className="button primary" disabled title={preview ? 'Render the sample with the local export CLI.' : 'Available when the backend provides the MP4.'}>
          <ControlIcon name="download" />{exportPending ? `Rendering ${Math.round((job?.progress ?? 0) * 100)}%` : 'MP4 unavailable'}</button>}
      <a className="button secondary" href={response?.media.srt ?? srt}
        download={`${props.lesson.lesson_id}_${props.lesson.language}.srt`}><ControlIcon name="download" />Subtitles (.SRT)</a></div>
      <a className="another-lesson" href="#/">Generate another lesson →</a>
      {preview && <p className="download-note">Hand-written sample. MP4 download becomes available after rendering.</p>}
      {exportFailed && <div className="notice error export-error" role="alert"><strong>Video export failed</strong><span>The lesson is still ready to watch.</span><a href="#/">Try again</a></div>}
    </div>
    <details className="lesson-diagnostics"><summary>Lesson details & warnings</summary><p>{preview ? 'Supplied sample with an estimated mock timeline.' : `Variant: ${props.timeline.variant}`}</p>
      {(response?.meta.warnings ?? props.lesson.warnings).length > 0 ? <ul>{(response?.meta.warnings ?? props.lesson.warnings).map((warning, i) => <li key={i}>{warning}</li>)}</ul> : <p>No lesson warnings.</p>}
      {job && <><p><strong>Device profile:</strong> {job.device_profile.toUpperCase()}</p><table><caption>Measured backend stage telemetry</caption><thead><tr><th>Stage</th><th>Milliseconds</th><th>Peak RAM</th></tr></thead>
        <tbody>{job.stages.map((stage) => <tr key={stage.name}><td>{stage.name}</td><td>{stage.ms === null ? '—' : `${stage.ms} ms`}</td><td>{stage.rss_mb === null ? '—' : `${stage.rss_mb} MB`}</td></tr>)}</tbody></table></>}
    </details>
  </div><aside className="lesson-sidebar" aria-label="Lesson navigation and settings"><section className="chapters-card">
    <div className="section-heading"><h2>Lesson Chapters</h2><span className="tag">{props.timeline.scenes.length} SCENES</span></div>
    <div className="scene-chips" aria-label="Jump to scene">{props.timeline.scenes.map((scene, n) =>
      <button key={scene.scene_id} className={index === n ? 'selected' : ''} aria-current={index === n ? 'step' : undefined}
        onClick={() => seek(scene.start_frame)}><span className="chapter-number">{String(n + 1).padStart(2, '0')}</span>
        <span className="chapter-copy">{props.lesson.scenes.find((item) => item.id === scene.scene_id)?.heading ?? scene.type}
          <small className="chapter-time">{timecode(scene.start_frame / props.timeline.fps)}{index === n ? ' · Now viewing' : ''}</small></span>
        {index === n && <span className="chapter-active" aria-hidden="true">▸</span>}</button>)}</div>
    <p className="playback-position">Scene {index + 1} of {props.timeline.scenes.length} · Click a chapter to jump in</p>
  </section><section className="settings-card"><h2>Lesson Settings</h2><dl className="lesson-settings">
    <div><dt>Language</dt><dd lang={props.lesson.language}>{language}</dd></div>
    <div><dt>Voice</dt><dd>{voice}</dd></div>
    <div><dt>Captions</dt><dd className={captions ? 'captions-on' : ''}>{captions ? 'On' : 'Off'}</dd></div>
    <div><dt>Difficulty</dt><dd>{props.lesson.level === 'beginner' ? 'Beginner' : 'Intermediate'}</dd></div>
  </dl><p className="sidebar-tip">Learn at your pace. Pause, replay, or jump to the part you need.</p></section></aside></div>;
}
