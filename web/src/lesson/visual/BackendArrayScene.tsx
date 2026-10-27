import {useMemo} from 'react';
import {useCurrentFrame} from 'remotion';
import type {RenderProps} from '../types';
import {Diagram} from '../scenes/Diagram';
import {fontFamily} from '../fonts';
import {fitFontSize, theme} from '../theme';
import {relativeToAbsolute} from '../timing';
import {arrayBox, arrayObjectState, prepareArrayScene} from './backendArray';

/** Optional validated sidecar entry point. No topic selection or automatic planning. */
export function BackendArrayScene({visualSpec, renderProps, sceneId}: {
  visualSpec: unknown; renderProps: RenderProps; sceneId: string;
}) {
  const relativeFrame = useCurrentFrame();
  const result = useMemo(() => {
    try {return {prepared: prepareArrayScene(visualSpec, renderProps, sceneId), error: ''};}
    catch (error) {return {prepared: null, error: error instanceof Error ? error.message : 'Invalid visual specification'};}
  }, [visualSpec, renderProps, sceneId]);
  const scene = renderProps.lesson.scenes.find((item) => item.id === sceneId);
  const timed = renderProps.timeline.scenes.find((item) => item.scene_id === sceneId);
  if (!scene || scene.type !== 'diagram' || !timed) throw new Error('Missing trusted legacy diagram');
  if (!result.prepared) return <div data-backend-fallback={result.error} style={{position: 'absolute', inset: 0}}><Diagram scene={scene} timelineScene={timed} language={renderProps.lesson.language} /></div>;
  const prepared = result.prepared;
  const frame = relativeToAbsolute(relativeFrame, timed);
  return <svg data-backend-visual={sceneId} data-layout="array_grid" lang={prepared.language}
    width={1280} height={720} viewBox="0 0 1280 720" style={{position: 'absolute', inset: 0}}>
    {prepared.objects.map((object) => {
      const box = arrayBox(object), state = arrayObjectState(prepared, object, frame);
      const label = prepared.labels.get(object.id);
      return <g key={object.id} data-backend-object={object.id} data-backend-kind={object.kind} opacity={state.opacity}>
        {object.kind !== 'text' && <rect x={box.x} y={box.y} width={box.width} height={box.height}
          rx={theme.boxRadius} fill={object.kind === 'highlight_region' ? 'none' : state.fill} stroke={state.stroke} strokeWidth={3} />}
        {label !== undefined && <text lang={prepared.language} x={box.x + box.width / 2} y={box.y + box.height / 2}
          dominantBaseline="middle" textAnchor="middle" fontFamily={fontFamily(prepared.language)}
          fontSize={fitFontSize(36, label, Math.max(1, Math.floor(box.width / 22)))} fontWeight={600} fill={object.kind === 'text' ? state.stroke : theme.ink}>{label}</text>}
      </g>;
    })}
  </svg>;
}
