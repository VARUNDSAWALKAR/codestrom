export type Language = 'en' | 'hi' | 'kn' | 'ta' | 'te' | 'bn' | 'mr';
export type CodeLanguage = 'python' | 'javascript' | 'java' | 'c' | 'cpp' | 'other';

export interface Step {
  text: string;
  narration: string;
  note?: string;
}

export interface CodeStep extends Step {
  lines: number[];
  output?: string;
}

export interface FormulaStep extends Step {
  note: string;
  in_expression?: boolean;
}

interface SceneBase {
  id: string;
  heading: string;
  narration: string;
}

export interface TitleCardScene extends SceneBase {
  type: 'title_card';
  subtitle?: string;
  steps: [];
}

export interface CodeWalkthroughScene extends SceneBase {
  type: 'code_walkthrough';
  code: string;
  code_language: CodeLanguage;
  steps: CodeStep[];
}

export type DiagramScene = SceneBase & {
  type: 'diagram';
  steps: Step[];
} & (
  | {layout: 'flow'; center?: never}
  | {layout: 'cycle'; center?: string}
  | {layout: 'labelled'; center: string}
);

export interface FormulaScene extends SceneBase {
  type: 'formula';
  expression: string;
  steps: FormulaStep[];
}

export interface RecapScene extends SceneBase {
  type: 'recap';
  steps: Step[];
}

// Quiz belongs to v1.1 and is intentionally not part of the v1 contract.
export type Scene = TitleCardScene | CodeWalkthroughScene | DiagramScene | FormulaScene | RecapScene;
export type SceneType = Scene['type'];

export interface Lesson {
  schema_version: '1.0';
  lesson_id: string;
  topic: string;
  level: 'beginner' | 'intermediate';
  target_seconds: number;
  language: Language;
  source: 'llm' | 'fallback' | 'sample' | 'edited';
  model: string;
  prompt_version: string;
  warnings: string[];
  title: string;
  subject: 'programming' | 'physics' | 'chemistry' | 'biology' | 'math' | 'other';
  keep_terms: string[];
  scenes: Scene[];
}

export interface Caption {
  text: string;
  start_frame: number;
  end_frame: number;
}

export interface Beat {
  beat_id: string;
  step_index: number | null;
  start_frame: number;
  end_frame: number;
  captions: Caption[];
}

export interface TimelineScene {
  scene_id: string;
  type: SceneType;
  start_frame: number;
  duration_frames: number;
  beats: Beat[];
}

export interface Timeline {
  timeline_version: 1;
  lesson_id: string;
  language: Language;
  variant: string;
  fps: number;
  width: number;
  height: number;
  duration_frames: number;
  audio: {web: string; wav: string} | null;
  voice: {engine: string; voice_id: string; speed: number};
  tempo: number;
  scenes: TimelineScene[];
}

// A type alias also satisfies Remotion's Record<string, unknown> props constraint.
export type RenderProps = {
  lesson: Lesson;
  timeline: Timeline;
  mediaBase: string;
  audioVariant: 'web' | 'wav';
  showCaptions: boolean;
};
