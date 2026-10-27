import {useCurrentFrame} from 'remotion';
import {sceneBoundaries} from '../timing';
import {grid, theme} from '../theme';
import type {Timeline} from '../types';

export function ProgressBar({timeline}: {timeline: Timeline}) {
  const frame = useCurrentFrame();
  const progress = Math.max(0, Math.min(1, frame / timeline.duration_frames));
  return <div data-chrome="progress" role="progressbar" aria-label="Lesson progress"
    aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}
    style={{position: 'absolute', left: 0, right: 0, top: grid.progressTop,
      height: grid.progressHeight, background: theme.progressTrack}}>
    <div style={{width: `${progress * 100}%`, height: '100%', background: theme.accent}} />
    {sceneBoundaries(timeline).map((boundary) => <div key={boundary} style={{position: 'absolute',
      left: `${boundary / timeline.duration_frames * 100}%`, top: 0, width: 2,
      height: '100%', background: theme.bg}} />)}
  </div>;
}
