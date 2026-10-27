import {Composition, registerRoot} from 'remotion';
import {ArrayDemo} from '../fixtures/ArrayDemo';
import {arrayDemoProps} from '../fixtures/arrayFixtureData';

function ArrayDemoRoot() {
  return <Composition id="BackendArrayDemo" component={ArrayDemo} width={1280} height={720}
    fps={arrayDemoProps.timeline.fps} durationInFrames={arrayDemoProps.timeline.duration_frames} defaultProps={{invalid: false}} />;
}
registerRoot(ArrayDemoRoot);
