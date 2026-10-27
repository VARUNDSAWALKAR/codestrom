export const theme = {
  bg: '#F7F9FC',
  surface: '#FFFFFF',
  ink: '#0F172A',
  ink2: '#475569',
  line: '#CBD5E1',
  accent: '#2563EB',
  accentSoft: '#DBEAFE',
  ok: '#16A34A',
  codeBg: '#0F172A',
  codeInk: '#E2E8F0',
  codeHl: 'rgba(59,130,246,0.28)',
  codeHlStrip: '#60A5FA',
  codeNumber: '#64748B',
  codeKeyword: '#93C5FD',
  codeString: '#86EFAC',
  codeLiteral: '#FCD34D',
  codeComment: '#94A3B8',
  capBg: 'rgba(15,23,42,0.88)',
  parts: ['#2563EB', '#0D9488', '#D97706', '#7C3AED', '#E11D48'],
  progressTrack: '#E2E8F0',
  boxRadius: 16,
  captionRadius: 12,
} as const;

export const grid = {
  width: 1280, height: 720, margin: 64,
  contentTop: 120, contentBottom: 580,
  captionTop: 604, captionBottom: 692,
  progressTop: 714, progressHeight: 6,
} as const;

export const typography = {
  title: {latin: 56, indic: 50, weight: 600, lineHeight: 1.25},
  heading: {latin: 34, indic: 32, weight: 600, lineHeight: 1.3},
  label: {latin: 28, indic: 26, weight: 600, lineHeight: 1.35},
  note: {latin: 20, indic: 19, weight: 400, lineHeight: 1.4},
  code: {size: 24, weight: 400, lineHeight: 34},
  formula: {size: 76, weight: 600, lineHeight: 1.1},
  recap: {latin: 32, indic: 30, weight: 400, lineHeight: 1.45},
  caption: {latin: 30, indic: 28, weight: 500, latinLineHeight: 1.4, indicLineHeight: 1.6},
  counter: {size: 20, weight: 400},
} as const;

export const fitFontSize = (size: number, text: string, maxChars: number): number =>
  size * Math.max(0.7, Math.min(1, maxChars / Math.max(1, Array.from(text).length)));
