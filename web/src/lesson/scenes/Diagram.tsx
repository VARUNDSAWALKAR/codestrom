import {useMemo} from 'react';
import type {DiagramScene, Language, TimelineScene} from '../types';
import {diagramVisualSpec, VisualSpecRenderer} from '../visual';

export function Diagram({scene, timelineScene, language}: {
  scene: DiagramScene; timelineScene: TimelineScene; language: Language;
}) {
  const spec = useMemo(() => diagramVisualSpec(scene, timelineScene, language), [scene, timelineScene, language]);
  return <VisualSpecRenderer spec={spec} timelineScene={timelineScene} />;
}
