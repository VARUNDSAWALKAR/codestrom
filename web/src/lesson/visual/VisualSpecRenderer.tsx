import {useMemo} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {relativeToAbsolute} from '../timing';
import type {RenderProps, TimelineScene} from '../types';
import type {RenderVisualSpec} from './types';
import {SvgPrimitive} from './SvgPrimitive';
import {interpretVisualSpec} from './interpreter';
import {BackendArrayScene} from './BackendArrayScene';

type RendererProps = {spec: RenderVisualSpec; timelineScene: TimelineScene} |
  {backendSpec: unknown; renderProps: RenderProps; sceneId: string};

export function VisualSpecRenderer(props: RendererProps) {
  if ('backendSpec' in props) return <BackendArrayScene visualSpec={props.backendSpec}
    renderProps={props.renderProps} sceneId={props.sceneId} />;
  return <InternalVisualSpecRenderer {...props} />;
}

function InternalVisualSpecRenderer({spec, timelineScene}: {spec: RenderVisualSpec; timelineScene: TimelineScene}) {
  const relativeFrame = useCurrentFrame(); const {fps} = useVideoConfig();
  const absoluteFrame = relativeToAbsolute(relativeFrame, timelineScene);
  const interpreted = useMemo(() => interpretVisualSpec(spec, timelineScene), [spec, timelineScene]);
  return <svg data-visual-spec={interpreted.id} data-layout={interpreted.layout} width={interpreted.width} height={interpreted.height}
    viewBox={`0 0 ${interpreted.width} ${interpreted.height}`} lang={interpreted.language} style={{position: 'absolute', inset: 0, overflow: 'hidden', background: interpreted.background}}>
    {interpreted.primitives.map((primitive) => <SvgPrimitive key={primitive.id} primitive={primitive} timelineScene={timelineScene} absoluteFrame={absoluteFrame} fps={fps} language={interpreted.language} />)}
  </svg>;
}

