import {interpolate, useCurrentFrame} from 'remotion';
import {fontFamily, isIndic} from '../fonts';
import {fitFontSize, grid, theme, typography} from '../theme';
import type {Language} from '../types';

export function StepHeading({heading, language, sceneNumber, sceneCount}: {
  heading: string; language: Language; sceneNumber: number; sceneCount: number;
}) {
  const frame = useCurrentFrame(); // Sequence-relative.
  const opacity = interpolate(frame, [0, 12], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  return <header lang={language} style={{position: 'absolute', left: grid.margin, right: grid.margin,
    top: 20, height: 76, display: 'flex', alignItems: 'center', gap: 24, opacity,
    fontFamily: fontFamily(language), color: theme.ink}}>
    <div data-chrome="heading" style={{flex: 1, minWidth: 0, overflow: 'hidden',
      display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
      fontSize: fitFontSize(isIndic(language) ? typography.heading.indic : typography.heading.latin, heading, 44),
      fontWeight: typography.heading.weight, lineHeight: typography.heading.lineHeight}}>{heading}</div>
    <span style={{fontSize: typography.counter.size, color: theme.ink2, flexShrink: 0}}>{sceneNumber} / {sceneCount}</span>
  </header>;
}
