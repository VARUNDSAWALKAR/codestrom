import {useId, useMemo} from 'react';
import {interpolateColors, useCurrentFrame, useVideoConfig} from 'remotion';
import {isIndic} from '../fonts';
import {relativeToAbsolute} from '../timing';
import {theme} from '../theme';
import type {DiagramScene, Language, TimelineScene} from '../types';
import {diagramGeometry} from './geometry';
import {enter, ramp, stepMotion} from './motion';
import {Text} from './Text';

export function Diagram({scene, timelineScene, language}: {
  scene: DiagramScene; timelineScene: TimelineScene; language: Language;
}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const absoluteFrame = relativeToAbsolute(frame, timelineScene);
  const geometry = useMemo(() => diagramGeometry(scene.layout, scene.steps.length), [scene.layout, scene.steps.length]);
  const marker = `arrow-${useId().replaceAll(':', '')}`;
  return <svg data-diagram-layout={scene.layout} width={1280} height={720} viewBox="0 0 1280 720"
    lang={language} style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
    <defs><marker id={marker} markerWidth={8} markerHeight={8} refX={7} refY={4} orient="auto" markerUnits="userSpaceOnUse">
      <path d="M 0 0 L 8 4 L 0 8 Z" fill={theme.accent} />
    </marker></defs>
    {geometry.connectors.map((connector, index) => {
      const motion = stepMotion(timelineScene, connector.reveal, absoluteFrame, fps);
      // A cycle's closing arrow starts with the final step, not the first.
      const amount = motion.beat ? ramp(absoluteFrame - motion.beat.start_frame + 3, 15) : 0;
      if (amount === 0) return null;
      return <g key={index} data-connector-to={connector.to} data-connector-from={connector.from} opacity={amount}>
        <path d={connector.path} pathLength={1} fill="none" stroke={theme.accent} strokeWidth={3}
          strokeDasharray={1} strokeDashoffset={1 - amount} markerEnd={scene.layout === 'labelled' || amount < 1 ? undefined : `url(#${marker})`} />
      </g>;
    })}
    {scene.layout !== 'flow' && scene.center && <g opacity={enter(frame, fps)} data-diagram="center">
      {scene.layout === 'cycle' ? <circle cx={640} cy={350} r={70} fill={theme.surface} stroke={theme.line} strokeWidth={2} /> :
        <rect x={510} y={302} width={260} height={96} rx={theme.boxRadius} fill={theme.surface} stroke={theme.line} strokeWidth={2} />}
      <foreignObject x={scene.layout === 'cycle' ? 580 : 526} y={310} width={scene.layout === 'cycle' ? 120 : 228} height={80}>
        <div style={{height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center'}}>
          <Text text={scene.center} language={language} size={isIndic(language) ? 24 : 26} bucket={scene.layout === 'cycle' ? 12 : 18}
            style={{fontWeight: 600, lineHeight: 1.35}} />
        </div>
      </foreignObject>
    </g>}
    {geometry.boxes.map((box, index) => {
      const step = scene.steps[index];
      const motion = stepMotion(timelineScene, index, absoluteFrame, fps);
      if (!step || motion.state === 'hidden') return null;
      const noteY = box.y + box.height / 2 + 8;
      const safeNoteY = noteY + 42 > 580 ? box.y - box.height / 2 - 46 : noteY;
      // Side notes sit inside the cycle, clear of its directional arrows.
      const sideNote = scene.layout === 'cycle' && Math.abs(box.x - 640) > 150;
      const noteWidth = sideNote ? 140 : box.width;
      const noteX = sideNote ? box.x > 640 ? box.x - box.width / 2 - 148 : box.x + box.width / 2 + 8 : box.x - box.width / 2;
      return <g key={index} data-diagram-step={index} data-step-state={motion.state}
        opacity={motion.entrance} transform={`translate(0 ${12 * (1 - motion.entrance)})`}>
        <rect data-diagram-box={index} x={box.x - box.width / 2} y={box.y - box.height / 2}
          width={box.width} height={box.height} rx={theme.boxRadius} strokeWidth={2}
          fill={interpolateColors(motion.activation, [0, 1], [theme.surface, theme.accentSoft])}
          stroke={interpolateColors(motion.activation, [0, 1], [theme.line, theme.accent])} />
        <foreignObject x={box.x - box.width / 2 + 12} y={box.y - box.height / 2 + 8} width={box.width - 24} height={box.height - 16}>
          <div style={{height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center'}}>
            <Text text={step.text} language={language} size={Math.min(isIndic(language) ? 26 : 28,
              (box.width - 24) / (Math.max(1, ...step.text.split(/\s+/).map((word) => Array.from(word).length)) * 0.65))} bucket={18}
              style={{fontWeight: 600, lineHeight: 1.35}} />
          </div>
        </foreignObject>
        {step.note && <foreignObject x={noteX} y={sideNote ? box.y - 21 : safeNoteY} width={noteWidth} height={42}>
          <Text text={step.note} language={language} size={isIndic(language) ? 19 : 20} bucket={Math.min(24, Math.floor(noteWidth / 12.4))}
            style={{color: theme.ink2, lineHeight: 1.4, textAlign: 'center'}} />
        </foreignObject>}
        {scene.layout === 'labelled' && <circle cx={box.x < 640 ? box.x + box.width / 2 : box.x > 640 ? box.x - box.width / 2 : box.x}
          cy={box.x === 640 ? box.y - box.height / 2 : box.y} r={4} fill={theme.accent} />}
      </g>;
    })}
  </svg>;
}
