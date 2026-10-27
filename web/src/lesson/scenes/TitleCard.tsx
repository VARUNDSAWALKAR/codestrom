import {useCurrentFrame, useVideoConfig} from 'remotion';
import {isIndic} from '../fonts';
import {theme, typography} from '../theme';
import type {Language, TitleCardScene} from '../types';
import {enter, ramp} from './motion';
import {Text} from './Text';

export function TitleCard({scene, language}: {scene: TitleCardScene; language: Language}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const heading = enter(frame, fps);
  const subtitle = enter(frame - 6, fps);
  return <>
    <Text text="Blu VisualTeacher" language={language} size={20} bucket={24}
      style={{position: 'absolute', left: 64, top: 36, color: theme.ink2}} />
    <div data-title="content" style={{position: 'absolute', left: 120, right: 120, top: 200,
      height: 320, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 24}}>
      <Text text={scene.heading} language={language} size={isIndic(language) ? 50 : 56} bucket={44}
        style={{maxWidth: '100%', textAlign: 'center', fontWeight: 600, lineHeight: typography.title.lineHeight,
          opacity: heading, transform: `translateY(${12 * (1 - heading)}px)`}} />
      {scene.subtitle && <Text text={scene.subtitle} language={language} size={28} bucket={55}
        style={{maxWidth: '100%', textAlign: 'center', lineHeight: 1.5, color: theme.ink2, opacity: subtitle,
          transform: `translateY(${12 * (1 - subtitle)}px)`}} />}
      <div style={{height: 4, width: 160 * ramp(frame - 10, 15), background: theme.accent, flexShrink: 0}} />
    </div>
  </>;
}
