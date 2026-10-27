import {useMemo} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from '../fonts';
import {relativeToAbsolute} from '../timing';
import {fitFontSize, theme} from '../theme';
import type {FormulaScene, Language, TimelineScene} from '../types';
import {ramp, stepMotion} from './motion';
import {Text} from './Text';

export function formulaSegments(scene: FormulaScene) {
  const matches = scene.steps.flatMap((step, index) => {
    const start = step.in_expression === false ? -1 : scene.expression.indexOf(step.text);
    return start < 0 || !step.text ? [] : [{start, end: start + step.text.length, index}];
  }).sort((a, b) => a.start - b.start);
  const segments: {text: string; index: number | null}[] = [];
  let cursor = 0;
  for (const match of matches) {
    if (match.start < cursor) continue;
    if (match.start > cursor) segments.push({text: scene.expression.slice(cursor, match.start), index: null});
    segments.push({text: scene.expression.slice(match.start, match.end), index: match.index});
    cursor = match.end;
  }
  if (cursor < scene.expression.length) segments.push({text: scene.expression.slice(cursor), index: null});
  return segments;
}

export function Formula({scene, timelineScene, language}: {
  scene: FormulaScene; timelineScene: TimelineScene; language: Language;
}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const absolute = relativeToAbsolute(frame, timelineScene);
  const segments = useMemo(() => formulaSegments(scene), [scene]);
  return <>
    <div lang={language} data-formula="expression" style={{position: 'absolute', left: 64, right: 64,
      top: 190, height: 110, display: 'flex', justifyContent: 'center', alignItems: 'center', whiteSpace: 'pre',
      fontFamily: fontFamily(language), fontSize: fitFontSize(76, scene.expression, 25), fontWeight: 600, lineHeight: 1.1}}>
      {segments.map((segment, i) => {
        const motion = segment.index === null ? undefined : stepMotion(timelineScene, segment.index, absolute, fps);
        const shown = motion && motion.state !== 'hidden';
        const color = shown ? theme.parts[(segment.index ?? 0) % theme.parts.length] : theme.ink;
        return <span key={i} data-formula-part={segment.index ?? undefined} style={{position: 'relative', color,
          transform: `scale(${motion ? 1 + 0.06 * motion.activation : 1})`}}>{segment.text}
          {shown && <span style={{position: 'absolute', left: 0, bottom: -10, height: 6,
            width: `${ramp(motion.age, 10) * 100}%`, background: color}} />}
        </span>;
      })}
    </div>
    {scene.steps.map((step, index) => {
      const motion = stepMotion(timelineScene, index, absolute, fps);
      if (motion.state === 'hidden') return null;
      return <div key={index} data-formula-step={index} data-step-state={motion.state}
        style={{position: 'absolute', left: 280, right: 100, top: 340 + index * 44, height: 44,
          display: 'flex', alignItems: 'center', gap: 12, opacity: motion.entrance,
          transform: `translateY(${12 * (1 - motion.entrance)}px)`}}>
        <span style={{width: 10, height: 10, borderRadius: '50%', background: theme.parts[index % theme.parts.length], flexShrink: 0}} />
        <Text text={`${step.text} — ${step.note}`} language={language} size={26} bucket={50} style={{lineHeight: 1.4}} />
      </div>;
    })}
  </>;
}
