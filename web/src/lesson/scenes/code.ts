import type {CodeLanguage, CodeWalkthroughScene, TimelineScene} from '../types';

export interface LineRun {start: number; count: number}
export function lineRuns(lines: readonly number[]): LineRun[] {
  const result: LineRun[] = [];
  for (const line of [...new Set(lines)].sort((a, b) => a - b)) {
    const last = result.at(-1);
    if (last && last.start + last.count === line) last.count++;
    else result.push({start: line, count: 1});
  }
  return result;
}

export function codeState(scene: CodeWalkthroughScene, timeline: TimelineScene, frame: number) {
  const steps = timeline.beats.filter((beat) => beat.step_index !== null && beat.start_frame <= frame);
  const beat = steps.at(-1);
  const step = beat?.step_index == null ? undefined : scene.steps[beat.step_index];
  const previousBeat = steps.at(-2);
  const previous = previousBeat?.step_index == null ? undefined : scene.steps[previousBeat.step_index];
  const output = steps.flatMap((item) => {
    const printed = item.step_index === null ? '' : scene.steps[item.step_index]?.output ?? '';
    if (!printed) return [];
    const lines = printed.split('\n');
    const count = Math.min(lines.length, 1 + Math.floor((frame - item.start_frame) * lines.length /
      Math.max(1, item.end_frame - item.start_frame)));
    return lines.slice(0, count);
  });
  return {beat, step, runs: lineRuns(step?.lines ?? []), previousRuns: lineRuns(previous?.lines ?? []), output};
}

const keywords: Record<CodeLanguage, Set<string>> = {
  python: new Set('for in range print if else elif while def return import from as class True False None and or not break continue'.split(' ')),
  javascript: new Set('const let var function return for of in if else while class new true false null undefined console'.split(' ')),
  java: new Set('public private protected static void int double float boolean class new return for if else while true false null System'.split(' ')),
  c: new Set('int float double char void return for while if else struct const sizeof printf include'.split(' ')),
  cpp: new Set('int float double char void return for while if else class struct const auto namespace using std cout include'.split(' ')),
  other: new Set(),
};
export type TokenKind = 'plain' | 'keyword' | 'string' | 'number' | 'comment';
/** Lexical colouring only: the supplied code is always rendered as text. */
export function tokenize(line: string, language: CodeLanguage): {text: string; kind: TokenKind}[] {
  if (language === 'other') return [{text: line, kind: 'plain'}];
  const tokens = line.match(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\/.*|#.*|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*\b|\s+|./g) ?? [];
  return tokens.map((text) => ({text, kind: text.startsWith('//') || (language === 'python' && text.startsWith('#')) ? 'comment' :
    /^['"]/.test(text) ? 'string' : /^\d/.test(text) ? 'number' : keywords[language].has(text) ? 'keyword' : 'plain'}));
}
