import {useEffect} from 'react';
import {AbsoluteFill, cancelRender, Sequence} from 'remotion';
import {BackendArrayScene} from '../lesson/visual/BackendArrayScene';
import {loadLessonFonts} from '../lesson/fonts';
import {StepHeading} from '../lesson/chrome/StepHeading';
import {CaptionBar} from '../lesson/chrome/CaptionBar';
import {ProgressBar} from '../lesson/chrome/ProgressBar';
import {theme} from '../lesson/theme';
import {arrayDemoFixture, arrayDemoProps} from './arrayFixtureData';

export function ArrayDemo({invalid = false}: {invalid?: boolean}) {
  useEffect(() => {void loadLessonFonts('en').catch(cancelRender);}, []);
  const scene = arrayDemoProps.timeline.scenes.find((item) => item.scene_id === 's2')!;
  return <AbsoluteFill style={{background: theme.bg, color: theme.ink}}>
    <StepHeading heading={arrayDemoProps.lesson.title} language="en" sceneNumber={1} sceneCount={1} />
    <Sequence from={scene.start_frame} durationInFrames={scene.duration_frames}>
      <BackendArrayScene visualSpec={invalid ? {...arrayDemoFixture.spec, visual_schema_version: 'invalid'} : arrayDemoFixture.spec}
        renderProps={arrayDemoProps} sceneId="s2" />
    </Sequence>
    <CaptionBar timeline={arrayDemoProps.timeline} language="en" showCaptions />
    <ProgressBar timeline={arrayDemoProps.timeline} />
  </AbsoluteFill>;
}
