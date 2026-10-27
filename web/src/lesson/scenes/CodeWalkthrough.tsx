import {useMemo} from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {monoFontFamily} from '../fonts';
import {relativeToAbsolute} from '../timing';
import {theme} from '../theme';
import type {CodeWalkthroughScene, Language, TimelineScene} from '../types';
import {codeState, tokenize} from './code';
import {clamp, enter, ramp} from './motion';
import {Text} from './Text';

export function CodeWalkthrough({scene, timelineScene, language}: {
  scene: CodeWalkthroughScene; timelineScene: TimelineScene; language: Language;
}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const state = codeState(scene, timelineScene, relativeToAbsolute(frame, timelineScene));
  const lines = useMemo(() => scene.code.split('\n'), [scene.code]);
  const tokens = useMemo(() => lines.map((line) => tokenize(line, scene.code_language)), [lines, scene.code_language]);
  const lineHeight = Math.min(34, 392 / lines.length);
  const codeSize = Math.min(24, lineHeight / 1.35, 596 / (Math.max(...lines.map((line) => Array.from(line).length), 1) * 0.62));
  const progress = state.beat ? ramp(relativeToAbsolute(frame, timelineScene) - state.beat.start_frame, 8) : 0;
  const colors = {plain: theme.codeInk, keyword: theme.codeKeyword, string: theme.codeString,
    number: theme.codeLiteral, comment: theme.codeComment};
  const opacity = enter(frame, fps);
  return <>
    <div data-code="panel" lang={language} style={{position: 'absolute', left: 64, top: 128, width: 696,
      height: 440, background: theme.codeBg, borderRadius: theme.boxRadius, overflow: 'hidden', opacity}}>
      {state.runs.map((run, index) => {
        const previous = state.previousRuns[index] ?? run;
        const y = interpolate(progress, [0, 1], [previous.start - 1, run.start - 1], clamp) * lineHeight;
        const height = interpolate(progress, [0, 1], [previous.count, run.count], clamp) * lineHeight;
        return <div key={index} data-code-highlight={run.start} data-line-count={run.count}
          style={{position: 'absolute', left: 0, right: 0, top: 24 + y, height,
            background: theme.codeHl, borderLeft: `4px solid ${theme.codeHlStrip}`, boxSizing: 'border-box',
            opacity: state.previousRuns.length ? 1 : progress}} />;
      })}
      <div style={{position: 'relative', padding: '24px 24px', fontFamily: monoFontFamily, fontSize: codeSize,
        lineHeight: `${lineHeight}px`, whiteSpace: 'pre'}}>
        {tokens.map((line, index) => <div data-code-line={index + 1} key={index} style={{display: 'flex'}}>
          <span aria-hidden="true" style={{width: 48, flexShrink: 0, color: theme.codeNumber}}>{index + 1}</span>
          <code style={{font: 'inherit', color: theme.codeInk}}>{line.map((token, i) =>
            <span key={i} style={{color: colors[token.kind]}}>{token.text}</span>)}</code>
        </div>)}
      </div>
    </div>
    <div data-code="state" style={{position: 'absolute', left: 792, top: 128, width: 424, height: 172,
      boxSizing: 'border-box', padding: 24, background: theme.surface, border: `2px solid ${theme.line}`,
      borderRadius: theme.boxRadius, opacity}}>
      <Text text="State" language={language} size={20} bucket={24} style={{color: theme.ink2, marginBottom: 16}} />
      <Text text={state.step?.text ?? ''} language={language} size={30} bucket={24}
        style={{fontWeight: 600, lineHeight: 1.5}} />
    </div>
    <div data-code="output" style={{position: 'absolute', left: 792, top: 320, width: 424, height: 248,
      background: theme.codeBg, color: theme.codeInk, borderRadius: theme.boxRadius,
      boxSizing: 'border-box', padding: 24, overflow: 'hidden', opacity}}>
      <Text text="Output" language={language} size={20} bucket={24} style={{color: theme.codeInk, marginBottom: 12}} />
      <pre data-code-output="lines" lang={language} style={{margin: 0, fontFamily: monoFontFamily,
        fontSize: Math.min(24, 164 / Math.max(1, state.output.length) / 1.4,
          376 / (Math.max(1, ...state.output.map((line) => Array.from(line).length)) * 0.62)),
        lineHeight: 1.4, whiteSpace: 'pre', overflow: 'hidden'}}>{state.output.join('\n')}</pre>
    </div>
  </>;
}
