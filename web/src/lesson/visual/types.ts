import type {CodeLanguage, Language} from '../types';

export interface Point {x: number; y: number}

export interface PrimitiveStyle {
  fill?: string;
  stroke?: string;
  strokeWidth?: number;
  opacity?: number;
  lineCap?: 'butt' | 'round' | 'square';
  lineJoin?: 'miter' | 'round' | 'bevel';
  dash?: number[];
}

interface PrimitiveBase {
  id: string;
  style?: PrimitiveStyle;
  actions?: VisualAction[];
}

export interface RectPrimitive extends PrimitiveBase {
  type: 'rect'; x: number; y: number; width: number; height: number; rx?: number;
}
export interface CirclePrimitive extends PrimitiveBase {type: 'circle'; cx: number; cy: number; r: number}
export interface EllipsePrimitive extends PrimitiveBase {type: 'ellipse'; cx: number; cy: number; rx: number; ry: number}
export interface PolygonPrimitive extends PrimitiveBase {type: 'polygon'; points: Point[]}
export interface PathPrimitive extends PrimitiveBase {type: 'path'; d: string; pathLength?: number}
export interface ArrowPrimitive extends PrimitiveBase {
  type: 'arrow'; from: Point; to: Point; bend?: number; marker?: 'arrow' | 'dot' | 'none';
}
export interface TextPrimitive extends PrimitiveBase {
  type: 'text'; x: number; y: number; width: number; height: number; text: string;
  align?: 'start' | 'middle' | 'end'; fontSize?: number; fontWeight?: 400 | 500 | 600;
}
export interface GroupPrimitive extends PrimitiveBase {
  type: 'group'; transform?: string; children: VisualPrimitive[];
}

export type VisualPrimitive = RectPrimitive | CirclePrimitive | EllipsePrimitive | PolygonPrimitive |
  PathPrimitive | ArrowPrimitive | TextPrimitive | GroupPrimitive;

interface ActionBase {
  beatId: string;
  offsetFrames?: number;
  durationFrames?: number;
}
export interface RevealAction extends ActionBase {type: 'reveal'; fromScale?: number}
export interface DrawAction extends ActionBase {type: 'draw'}
export interface MoveAction extends ActionBase {type: 'move'; from: Point; to: Point}
export interface HighlightAction extends ActionBase {type: 'highlight'; color?: string}
export interface TransformValue {x?: number; y?: number; scale?: number; rotate?: number}
export interface TransformAction extends ActionBase {type: 'transform'; from: TransformValue; to: TransformValue}
export interface TraceAction extends ActionBase {type: 'trace'; color?: string}
export type VisualAction = RevealAction | DrawAction | MoveAction | HighlightAction | TransformAction | TraceAction;

export type LayoutKind = 'spatial' | 'flow' | 'grid' | 'network' | 'coordinate' | 'comparison' | 'code';

/** Internal pixel-space scene graph compiled by the renderer. Not the backend visual-v1 envelope. */
export interface RenderVisualSpec {
  version: 1;
  id: string;
  language: Language;
  width: 1280;
  height: 720;
  layout: LayoutKind;
  primitives: VisualPrimitive[];
  background?: string;
  code?: {source: string; language: CodeLanguage; activeLines: Record<string, number[]>};
}

