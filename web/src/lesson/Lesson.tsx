import {useEffect} from 'react';
import {AbsoluteFill, Audio, cancelRender, Sequence} from 'remotion';
import {CaptionBar} from './chrome/CaptionBar';
import {ProgressBar} from './chrome/ProgressBar';
import {StepHeading} from './chrome/StepHeading';
import {fontFamily, loadLessonFonts} from './fonts';
import {theme} from './theme';
import {TitleCard} from './scenes/TitleCard';
import {CodeWalkthrough} from './scenes/CodeWalkthrough';
import {Diagram} from './scenes/Diagram';
import {Formula} from './scenes/Formula';
import {Recap} from './scenes/Recap';
import type {Language, RenderProps, Scene, TimelineScene} from './types';

function SceneByType({scene, timelineScene, language}: {
  scene: Scene; timelineScene: TimelineScene; language: Language;
}) {
  switch (scene.type) {
    case 'title_card': return <TitleCard scene={scene} language={language} />;
    case 'code_walkthrough': return <CodeWalkthrough scene={scene} timelineScene={timelineScene} language={language} />;
    case 'diagram': return <Diagram scene={scene} timelineScene={timelineScene} language={language} />;
    case 'formula': return <Formula scene={scene} timelineScene={timelineScene} language={language} />;
    case 'recap': return <Recap scene={scene} timelineScene={timelineScene} language={language} />;
    default: { const exhaustive: never = scene; return exhaustive; }
  }
}

export function Lesson({lesson, timeline, mediaBase, audioVariant, showCaptions}: RenderProps) {
  useEffect(() => {
    void loadLessonFonts(lesson.language).catch(cancelRender);
  }, [lesson.language]);
  const contentScenes = timeline.scenes.filter((scene) => scene.type !== 'title_card');
  return <AbsoluteFill lang={lesson.language} style={{background: theme.bg, color: theme.ink,
    fontFamily: fontFamily(lesson.language), overflow: 'hidden'}}>
    {timeline.audio !== null && <Audio src={`${mediaBase}${timeline.audio[audioVariant]}`} />}
    {timeline.scenes.map((timedScene) => {
      const scene = lesson.scenes.find((item) => item.id === timedScene.scene_id);
      if (!scene || scene.type !== timedScene.type) throw new Error(`Lesson/timeline scene mismatch: ${timedScene.scene_id}`);
      return <Sequence key={timedScene.scene_id} name={scene.heading}
        from={timedScene.start_frame} durationInFrames={timedScene.duration_frames}>
        {scene.type !== 'title_card' && <StepHeading heading={scene.heading} language={lesson.language}
          sceneNumber={contentScenes.indexOf(timedScene) + 1} sceneCount={contentScenes.length} />}
        <div data-scene-id={scene.id} data-scene-type={scene.type} lang={lesson.language} style={{position: 'absolute', inset: 0}}>
          <SceneByType scene={scene} timelineScene={timedScene} language={lesson.language} />
        </div>
      </Sequence>;
    })}
    <CaptionBar timeline={timeline} language={lesson.language} showCaptions={showCaptions} />
    <ProgressBar timeline={timeline} />
  </AbsoluteFill>;
}
