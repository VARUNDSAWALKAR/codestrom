import {createRef} from 'react';
import {createRoot} from 'react-dom/client';
import {Player, type PlayerRef} from '@remotion/player';
import {ArrayDemo} from '../src/fixtures/ArrayDemo';
import {arrayDemoProps} from '../src/fixtures/arrayFixtureData';

const root = createRoot(document.getElementById('root')!);
const ref = createRef<PlayerRef>();
declare global {interface Window {arrayDemo: {seek: (frame: number) => void; mount: (invalid: boolean) => void}}}
window.arrayDemo = {
  seek: (frame) => {if (!ref.current) throw new Error('Player not mounted'); ref.current.seekTo(frame);},
  mount: (invalid) => root.render(<Player ref={ref} component={ArrayDemo} inputProps={{invalid}}
    durationInFrames={arrayDemoProps.timeline.duration_frames} fps={arrayDemoProps.timeline.fps}
    compositionWidth={1280} compositionHeight={720} style={{width: 1280, height: 720}} />),
};
window.arrayDemo.mount(false);
