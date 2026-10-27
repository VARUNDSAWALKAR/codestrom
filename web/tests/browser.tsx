import {createRef} from 'react';
import {createRoot} from 'react-dom/client';
import {Player, type PlayerRef} from '@remotion/player';
import {Lesson} from '../src/lesson/Lesson';
import type {RenderProps} from '../src/lesson/types';

const element = document.getElementById('root');
if (!element) throw new Error('Missing test root');
const root = createRoot(element);
const ref = createRef<PlayerRef>();
declare global {
  interface Window {
    lessonTest: {
      mount: (props: RenderProps) => void;
      seek: (frame: number) => void;
    };
  }
}
window.lessonTest = {
  mount: (props) => root.render(<Player ref={ref} component={Lesson} inputProps={props}
    durationInFrames={props.timeline.duration_frames} fps={props.timeline.fps}
    compositionWidth={1280} compositionHeight={720} style={{width: 1280, height: 720}} />),
  seek: (frame) => {
    if (!ref.current) throw new Error('Player not mounted');
    ref.current.seekTo(frame);
  },
};
