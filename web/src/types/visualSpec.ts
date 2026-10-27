import type {CodeLanguage, Language, SceneType} from '../lesson/types';

export type VisualSchemaVersion = 'visual-v1';
export type VisualStyle = 'primary' | 'secondary' | 'accent' | 'muted' | 'warning' | 'highlight';
export type VisualLayout = 'flow_cycle' | 'spatial' | 'array_grid' | 'graph_network' |
  'coordinate_plane' | 'comparison' | 'code_walkthrough';
export type RelationshipKind = 'connected_to' | 'contains' | 'points_toward' | 'aligned_with' |
  'before' | 'ordered_with' | 'belongs_to' | 'depends_on';

export interface VisualPoint {x: number; y: number}

export type SourceField = 'heading' | 'center' | 'expression' | 'code' | 'text' | 'note' | 'output';
export interface SourceLabel {kind: 'source'; field: SourceField; step_index: number | null}
export interface LiteralLabel {kind: 'literal'; text: string}
export type VisualLabel = SourceLabel | LiteralLabel;

interface VisualObjectBase {
  id: string;
  role: string;
  style: VisualStyle;
  label: VisualLabel | null;
}
export interface RectangleObject extends VisualObjectBase {kind: 'rectangle'; position: VisualPoint; width: number; height: number}
export interface CircleObject extends VisualObjectBase {kind: 'circle'; position: VisualPoint; radius: number}
export interface EllipseObject extends VisualObjectBase {kind: 'ellipse'; position: VisualPoint; rx: number; ry: number}
export interface PolygonObject extends VisualObjectBase {kind: 'polygon'; points: VisualPoint[]}
export interface LineObject extends VisualObjectBase {kind: 'line' | 'arrow'; start: VisualPoint; end: VisualPoint}
export interface LinePathSegment {kind: 'line'; end: VisualPoint}
export interface CubicPathSegment {kind: 'cubic'; control1: VisualPoint; control2: VisualPoint; end: VisualPoint}
export type VisualPathSegment = LinePathSegment | CubicPathSegment;
export interface PathObject extends VisualObjectBase {kind: 'path'; start: VisualPoint; segments: VisualPathSegment[]}
export interface TextObject extends VisualObjectBase {kind: 'text'; position: VisualPoint; label: VisualLabel; width: number; height: number}
export interface GroupObject extends VisualObjectBase {kind: 'group'; children: string[]}
export interface MarkerObject extends VisualObjectBase {kind: 'marker'; position: VisualPoint; radius: number}
export interface HighlightRegionObject extends VisualObjectBase {kind: 'highlight_region'; position: VisualPoint; width: number; height: number}
export interface ParticlesObject extends VisualObjectBase {kind: 'particles'; positions: VisualPoint[]; radius: number}
export interface AssetObject extends VisualObjectBase {kind: 'asset'; asset_id: string; position: VisualPoint; width: number; height: number}
export type VisualObject = RectangleObject | CircleObject | EllipseObject | PolygonObject | LineObject |
  PathObject | TextObject | GroupObject | MarkerObject | HighlightRegionObject | ParticlesObject | AssetObject;
/** Renderer terminology: a VisualSpec node is one typed visual object. */
export type VisualNode = VisualObject;

export interface VisualRelationship {kind: RelationshipKind; source: string; target: string}
/** Renderer terminology: semantic topology edges remain separate from drawable line/path objects. */
export type VisualEdge = VisualRelationship;

interface VisualActionBase {id: string; target: string; beat_id: string; start: number; end: number}
export interface RevealVisualAction extends VisualActionBase {kind: 'reveal'; from_opacity: number; to_opacity: number}
export interface DrawVisualAction extends VisualActionBase {kind: 'draw'; from_progress: number; to_progress: number}
export interface MoveVisualAction extends VisualActionBase {kind: 'move'; from_position: VisualPoint; to_position: VisualPoint}
export interface HighlightVisualAction extends VisualActionBase {kind: 'highlight'; from_style: VisualStyle; to_style: VisualStyle}
export interface TransformVisualAction extends VisualActionBase {kind: 'transform'; from_scale: number; to_scale: number; from_opacity: number; to_opacity: number}
export interface TraceVisualAction extends VisualActionBase {kind: 'trace'; path_id: string; from_progress: number; to_progress: number}
export type VisualAction = RevealVisualAction | DrawVisualAction | MoveVisualAction |
  HighlightVisualAction | TransformVisualAction | TraceVisualAction;

export type VisualFallbackCode = 'legacy_scene' | 'unsupported_mechanism' | 'source_inaccurate' |
  'invalid_candidate' | 'model_unavailable' | 'not_selected' | 'cache_invalid';
export interface VisualFallback {code: VisualFallbackCode; reason: string}

export interface SpecializedSceneVisual {
  scene_id: string;
  layout: VisualLayout;
  mechanism: string;
  accuracy: 'illustrative';
  limitations: string[];
  objects: VisualObject[];
  relationships: VisualRelationship[];
  actions: VisualAction[];
  fallback: null;
}
export interface FallbackSceneVisual {
  scene_id: string;
  layout: null;
  mechanism: string;
  accuracy: 'legacy';
  limitations: string[];
  objects: [];
  relationships: [];
  actions: [];
  fallback: VisualFallback;
}
export type SceneVisual = SpecializedSceneVisual | FallbackSceneVisual;

export interface VisualProvenance {
  prompt_version: string;
  model: string;
  model_identity: string;
  capability_version: string;
  asset_version: string;
  semantics_version: string;
  configuration_fingerprint: string;
}
export interface VisualSpec {
  visual_schema_version: VisualSchemaVersion;
  lesson_id: string;
  source_fingerprint: string;
  provenance: VisualProvenance;
  scenes: SceneVisual[];
}

// Timeline remains a separate measured clock. Visual action start/end values are fractions of these beats.
export interface VisualCaption {text: string; start_frame: number; end_frame: number}
export interface NarrationBeat {
  beat_id: string;
  step_index: number | null;
  start_frame: number;
  end_frame: number;
  captions: VisualCaption[];
}
export interface VisualSceneTimeline {
  scene_id: string;
  type: SceneType;
  start_frame: number;
  duration_frames: number;
  beats: NarrationBeat[];
}
export interface VisualTimeline {
  timeline_version: 1;
  lesson_id: string;
  language: Language;
  variant: string;
  fps: 30;
  width: 1280;
  height: 720;
  duration_frames: number;
  audio: {web: string; wav: string} | null;
  voice: {engine: 'kokoro' | 'parler' | 'mock'; voice_id: string; speed: number};
  tempo: number;
  scenes: VisualSceneTimeline[];
}
export interface BoundVisualAction {
  scene_id: string;
  action_id: string;
  beat_id: string;
  start_frame: number;
  end_frame: number;
}

// Canonical source shape serialized in the authored fixture envelopes.
export interface VisualFixtureStep {
  text: string; narration: string; note: string; lines: number[]; output: string; in_expression: boolean;
}
export interface VisualFixtureScene {
  id: string; type: SceneType; heading: string; narration: string; steps: VisualFixtureStep[];
  subtitle: string; code: string; code_language: CodeLanguage; layout: 'flow' | 'cycle' | 'labelled';
  center: string; expression: string;
}
export interface VisualFixtureLesson {
  schema_version: '1.0'; lesson_id: string; topic: string; level: 'beginner' | 'intermediate';
  target_seconds: number; language: Language; source: 'llm' | 'fallback' | 'sample' | 'edited';
  model: string; prompt_version: string; warnings: string[]; title: string;
  subject: 'programming' | 'physics' | 'chemistry' | 'biology' | 'math' | 'other'; keep_terms: string[];
  scenes: VisualFixtureScene[];
}
export interface VisualFixtureExpectation {
  layout: VisualLayout;
  objects: number;
  actions: number;
  specialized_scene_ids: string[];
  fallback_scenes: number;
}
export interface VisualFixture {
  origin: string;
  source: VisualFixtureLesson;
  spec: VisualSpec;
  expected: VisualFixtureExpectation;
  review_notes: string[];
}
export interface MockVisualFixture extends VisualFixture {timeline: VisualTimeline; bound_actions: BoundVisualAction[]; mock: true}
