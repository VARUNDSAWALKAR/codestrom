import type {CSSProperties} from 'react';
import {fontFamily} from '../fonts';
import {fitFontSize} from '../theme';
import type {Language} from '../types';

export function Text({text, language, size, bucket, style = {}}: {
  text: string; language: Language; size: number; bucket: number; style?: CSSProperties;
}) {
  return <div lang={language} style={{fontFamily: fontFamily(language),
    fontSize: fitFontSize(size, text, bucket), overflowWrap: 'anywhere',
    display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
    overflow: 'hidden', ...style}}>{text}</div>;
}
