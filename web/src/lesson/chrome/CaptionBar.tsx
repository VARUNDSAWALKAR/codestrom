import {interpolate, useCurrentFrame} from 'remotion';
import {fontFamily, isIndic} from '../fonts';
import {activeCaption} from '../timing';
import {fitFontSize, grid, theme, typography} from '../theme';
import type {Language, Timeline} from '../types';

export function CaptionBar({timeline, language, showCaptions}: {
  timeline: Timeline; language: Language; showCaptions: boolean;
}) {
  const frame = useCurrentFrame(); // Mounted outside scene Sequences: absolute.
  const caption = activeCaption(timeline, frame);
  if (!showCaptions || !caption) return null;
  const opacity = interpolate(frame - caption.start_frame, [0, 6], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const indic = isIndic(language);
  return <div data-chrome="caption" lang={language} style={{position: 'absolute',
    left: grid.margin, right: grid.margin, top: grid.captionTop, height: grid.captionBottom - grid.captionTop,
    boxSizing: 'border-box', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: theme.capBg, color: theme.surface, borderRadius: theme.captionRadius, opacity,
    fontFamily: fontFamily(language), textAlign: 'center'}}>
    <div style={{display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
      fontSize: fitFontSize(indic ? typography.caption.indic : typography.caption.latin, caption.text, 100),
      fontWeight: typography.caption.weight,
      lineHeight: indic ? typography.caption.indicLineHeight : typography.caption.latinLineHeight}}>{caption.text}</div>
  </div>;
}
