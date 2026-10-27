import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';
import type {Language} from './types';

const scripts = {
  en: null,
  hi: {family: 'Noto Sans Devanagari', slug: 'noto-sans-devanagari', subset: 'devanagari'},
  mr: {family: 'Noto Sans Devanagari', slug: 'noto-sans-devanagari', subset: 'devanagari'},
  kn: {family: 'Noto Sans Kannada', slug: 'noto-sans-kannada', subset: 'kannada'},
  ta: {family: 'Noto Sans Tamil', slug: 'noto-sans-tamil', subset: 'tamil'},
  te: {family: 'Noto Sans Telugu', slug: 'noto-sans-telugu', subset: 'telugu'},
  bn: {family: 'Noto Sans Bengali', slug: 'noto-sans-bengali', subset: 'bengali'},
} as const satisfies Record<Language, {family: string; slug: string; subset: string} | null>;

export const monoFontFamily = '"Noto Sans Mono", monospace';
export const isIndic = (language: Language): boolean => language !== 'en';
export const fontFamily = (language: Language): string => {
  const script = scripts[language];
  return script ? `"${script.family}", "Noto Sans", sans-serif` : '"Noto Sans", sans-serif';
};

const loaded = new Map<string, Promise<void>>();
function localFont(family: string, slug: string, subset: string, weight: number): Promise<void> {
  const key = `${slug}-${subset}-${weight}`;
  let promise = loaded.get(key);
  if (!promise) {
    promise = loadFont({
      family,
      url: staticFile(`fonts/${key}-normal.woff2`),
      weight: String(weight),
      style: 'normal',
    });
    loaded.set(key, promise);
  }
  return promise;
}

/** loadFont holds Remotion rendering until local FontFace assets are ready. */
export function loadLessonFonts(language: Language): Promise<void[]> {
  const fonts = [400, 500, 600].map((weight) => localFont('Noto Sans', 'noto-sans', 'latin', weight));
  fonts.push(localFont('Noto Sans Mono', 'noto-sans-mono', 'latin', 400));
  const script = scripts[language];
  if (script) {
    fonts.push(...[400, 500, 600].map((weight) => localFont(script.family, script.slug, script.subset, weight)));
  }
  return Promise.all(fonts);
}
