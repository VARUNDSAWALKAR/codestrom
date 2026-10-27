import {useCurrentFrame, useVideoConfig} from 'remotion';
import {isIndic} from '../fonts';
import {relativeToAbsolute} from '../timing';
import {theme} from '../theme';
import type {Language, RecapScene, TimelineScene} from '../types';
import {ramp, stepMotion} from './motion';
import {Text} from './Text';

export function Recap({scene, timelineScene, language}: {
  scene: RecapScene; timelineScene: TimelineScene; language: Language;
}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return <>{scene.steps.map((step, index) => {
    const motion = stepMotion(timelineScene, index, relativeToAbsolute(frame, timelineScene), fps);
    if (motion.state === 'hidden') return null;
    return <div key={index} data-recap-step={index} data-step-state={motion.state}
      style={{position: 'absolute', left: 160, right: 100, top: 170 + 96 * index,
        height: 88, display: 'flex', alignItems: 'flex-start', gap: 24, opacity: motion.entrance,
        transform: `translateY(${12 * (1 - motion.entrance)}px)`}}>
      <svg width={40} height={40} viewBox="0 0 40 40" style={{flexShrink: 0, marginTop: 3}} aria-hidden="true">
        <circle cx={20} cy={20} r={19} fill={theme.surface} stroke={theme.ok} strokeWidth={2} />
        <path d="M 10 20 L 17 27 L 30 13" fill="none" stroke={theme.ok} strokeWidth={3}
          pathLength={1} strokeDasharray={1} strokeDashoffset={1 - ramp(motion.age, 12)} />
      </svg>
      <Text text={step.text} language={language} size={isIndic(language) ? 30 : 32} bucket={40}
        style={{lineHeight: 1.45, color: motion.state === 'active' ? theme.ink : theme.ink2}} />
    </div>;
  })}</>;
}
