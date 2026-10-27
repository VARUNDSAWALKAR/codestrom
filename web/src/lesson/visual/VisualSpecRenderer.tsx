import {useMemo} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {relativeToAbsolute} from '../timing';
import type {TimelineScene} from '../types';
import type {VisualSpec} from './types';
import {SvgPrimitive} from './SvgPrimitive';
import {interpretVisualSpec} from './interpreter';

export function VisualSpecRenderer({spec, timelineScene}: {spec: VisualSpec; timelineScene: TimelineScene}) {
  const relativeFrame = useCurrentFrame(); const {fps} = useVideoConfig();
  const absoluteFrame = relativeToAbsolute(relativeFrame, timelineScene);
  const interpreted = useMemo(() => interpretVisualSpec(spec, timelineScene), [spec, timelineScene]);
  return <svg data-visual-spec={interpreted.id} data-layout={interpreted.layout} width={interpreted.width} height={interpreted.height}
    viewBox={`0 0 ${interpreted.width} ${interpreted.height}`} lang={interpreted.language} style={{position: 'absolute', inset: 0, overflow: 'hidden', background: interpreted.background}}>
    {interpreted.primitives.map((primitive) => <SvgPrimitive key={primitive.id} primitive={primitive} timelineScene={timelineScene} absoluteFrame={absoluteFrame} fps={fps} language={interpreted.language} />)}
  </svg>;
}

