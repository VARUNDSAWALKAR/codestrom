import {Composition, type CalculateMetadataFunction} from 'remotion';
import {Lesson} from '../lesson/Lesson';
import type {RenderProps} from '../lesson/types';
import {sampleProps} from './sampleProps';

export const calculateLessonMetadata: CalculateMetadataFunction<RenderProps> = ({props}) => ({
  durationInFrames: props.timeline.duration_frames,
  fps: props.timeline.fps,
});

export function RemotionRoot() {
  return <Composition id="Lesson" component={Lesson} width={1280} height={720}
    fps={sampleProps.timeline.fps} durationInFrames={sampleProps.timeline.duration_frames}
    defaultProps={sampleProps} calculateMetadata={calculateLessonMetadata} />;
}
