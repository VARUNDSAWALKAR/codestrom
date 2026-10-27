import {useId} from 'react';
import {fontFamily} from '../fonts';
import {fitFontSize, theme} from '../theme';
import type {Language, TimelineScene} from '../types';
import {resolveActions} from './animation';
import type {VisualPrimitive} from './types';

export function SvgPrimitive({primitive, timelineScene, absoluteFrame, fps, language}: {
  primitive: VisualPrimitive; timelineScene: TimelineScene; absoluteFrame: number; fps: number; language: Language;
}) {
  const markerId = `visual-arrow-${useId().replaceAll(':', '')}`;
  const animation = resolveActions(primitive.actions, timelineScene, absoluteFrame, fps);
  const style = primitive.style ?? {};
  const common = {opacity: animation.opacity * (style.opacity ?? 1), transform: animation.transform || undefined,
    fill: style.fill ?? 'none', stroke: animation.stroke ?? style.stroke, strokeWidth: style.strokeWidth,
    strokeLinecap: style.lineCap, strokeLinejoin: style.lineJoin, strokeDasharray: animation.strokeDasharray ?? style.dash?.join(' '),
    strokeDashoffset: animation.strokeDashoffset, filter: animation.filter, style: {transformBox: 'fill-box', transformOrigin: 'center'} as const};
  switch (primitive.type) {
    case 'rect': return <rect {...common} x={primitive.x} y={primitive.y} width={primitive.width} height={primitive.height} rx={primitive.rx} />;
    case 'circle': return <circle {...common} cx={primitive.cx} cy={primitive.cy} r={primitive.r} />;
    case 'ellipse': return <ellipse {...common} cx={primitive.cx} cy={primitive.cy} rx={primitive.rx} ry={primitive.ry} />;
    case 'polygon': return <polygon {...common} points={primitive.points.map((point) => `${point.x},${point.y}`).join(' ')} />;
    case 'path': return <path {...common} d={primitive.d} pathLength={primitive.pathLength ?? (animation.strokeDasharray ? 1 : undefined)} />;
    case 'arrow': {
      const bend = primitive.bend ?? 0; const midX = (primitive.from.x + primitive.to.x) / 2; const midY = (primitive.from.y + primitive.to.y) / 2;
      const d = bend === 0 ? `M ${primitive.from.x} ${primitive.from.y} L ${primitive.to.x} ${primitive.to.y}` : `M ${primitive.from.x} ${primitive.from.y} Q ${midX - (primitive.to.y - primitive.from.y) * bend} ${midY + (primitive.to.x - primitive.from.x) * bend} ${primitive.to.x} ${primitive.to.y}`;
      return <g><defs><marker id={markerId} markerWidth={8} markerHeight={8} refX={7} refY={4} orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L8 4 L0 8 Z" fill={animation.stroke ?? style.stroke ?? theme.accent} /></marker></defs><path {...common} d={d} pathLength={animation.strokeDasharray ? 1 : undefined} markerEnd={primitive.marker === 'none' ? undefined : `url(#${markerId})`} /></g>;
    }
    case 'text': {
      const anchor = primitive.align ?? 'start'; const x = anchor === 'middle' ? primitive.x + primitive.width / 2 : anchor === 'end' ? primitive.x + primitive.width : primitive.x;
      const size = fitFontSize(primitive.fontSize ?? 24, primitive.text, Math.max(4, Math.floor(primitive.width / ((primitive.fontSize ?? 24) * .58))));
      return <text {...common} lang={language} x={x} y={primitive.y + primitive.height / 2} dominantBaseline="middle" textAnchor={anchor} fill={style.fill ?? theme.ink} stroke="none" fontFamily={fontFamily(language)} fontSize={size} fontWeight={primitive.fontWeight ?? 400}>{primitive.text}</text>;
    }
    case 'group': return <g {...common} transform={[primitive.transform, animation.transform].filter(Boolean).join(' ') || undefined}>{primitive.children.map((child) => <SvgPrimitive key={child.id} primitive={child} timelineScene={timelineScene} absoluteFrame={absoluteFrame} fps={fps} language={language} />)}</g>;
    default: {const exhaustive: never = primitive; return exhaustive;}
  }
}

