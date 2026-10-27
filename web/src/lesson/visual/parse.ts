import type {Language} from '../types';
import type {PrimitiveStyle, RenderVisualSpec, VisualAction, VisualPrimitive} from './types';

type JsonObject = Record<string, unknown>;
const languages = ['en', 'hi', 'kn', 'ta', 'te', 'bn', 'mr'] as const;
const layouts = ['spatial', 'flow', 'grid', 'network', 'coordinate', 'comparison', 'code'] as const;
const codeLanguages = ['python', 'javascript', 'java', 'c', 'cpp', 'other'] as const;

function object(value: unknown, name: string): JsonObject {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${name} must be an object`);
  return value as JsonObject;
}
function array(value: unknown, name: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${name} must be an array`);
  return value;
}
function text(value: unknown, name: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${name} must be a non-empty string`);
  return value;
}
function paint(value: unknown, name: string): string {
  const result = text(value, name);
  if (/url\s*\(|https?:|\/\//i.test(result) || result.includes('\\')) throw new Error(`${name} must be an inline color`);
  return result;
}
function number(value: unknown, name: string, min = -Infinity): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min) throw new Error(`${name} must be a finite number`);
  return value;
}
function optionalNumber(value: unknown, name: string, min = -Infinity): number | undefined {
  return value === undefined ? undefined : number(value, name, min);
}
function choice<T extends string>(value: unknown, choices: readonly T[], name: string): T {
  if (typeof value !== 'string' || !choices.includes(value as T)) throw new Error(`Invalid ${name}`);
  return value as T;
}
function noUnknown(raw: JsonObject, allowed: readonly string[], name: string): void {
  const unknown = Object.keys(raw).find((key) => !allowed.includes(key));
  if (unknown) throw new Error(`${name} contains unknown field ${unknown}`);
}
function point(value: unknown, name: string) {
  const raw = object(value, name); noUnknown(raw, ['x', 'y'], name);
  return {x: number(raw.x, `${name}.x`), y: number(raw.y, `${name}.y`)};
}
function transform(value: unknown, name: string) {
  const raw = object(value, name); noUnknown(raw, ['x', 'y', 'scale', 'rotate'], name);
  const result: {x?: number; y?: number; scale?: number; rotate?: number} = {};
  for (const key of ['x', 'y', 'scale', 'rotate'] as const) if (raw[key] !== undefined) result[key] = number(raw[key], `${name}.${key}`, key === 'scale' ? 0 : -Infinity);
  if (Object.keys(result).length === 0) throw new Error(`${name} must contain a transform value`);
  return result;
}
function style(value: unknown, name: string): PrimitiveStyle | undefined {
  if (value === undefined) return undefined;
  const raw = object(value, name);
  noUnknown(raw, ['fill', 'stroke', 'strokeWidth', 'opacity', 'lineCap', 'lineJoin', 'dash'], name);
  const result: PrimitiveStyle = {};
  if (raw.fill !== undefined) result.fill = paint(raw.fill, `${name}.fill`);
  if (raw.stroke !== undefined) result.stroke = paint(raw.stroke, `${name}.stroke`);
  if (raw.strokeWidth !== undefined) result.strokeWidth = number(raw.strokeWidth, `${name}.strokeWidth`, 0);
  if (raw.opacity !== undefined) result.opacity = Math.min(1, number(raw.opacity, `${name}.opacity`, 0));
  if (raw.lineCap !== undefined) result.lineCap = choice(raw.lineCap, ['butt', 'round', 'square'], `${name}.lineCap`);
  if (raw.lineJoin !== undefined) result.lineJoin = choice(raw.lineJoin, ['miter', 'round', 'bevel'], `${name}.lineJoin`);
  if (raw.dash !== undefined) result.dash = array(raw.dash, `${name}.dash`).map((item, index) => number(item, `${name}.dash[${index}]`, 0));
  return result;
}
function action(value: unknown, name: string): VisualAction {
  const raw = object(value, name);
  const type = choice(raw.type, ['reveal', 'draw', 'move', 'highlight', 'transform', 'trace'], `${name}.type`);
  const common = {beatId: text(raw.beatId, `${name}.beatId`)};
  const offsetFrames = optionalNumber(raw.offsetFrames, `${name}.offsetFrames`);
  const durationFrames = optionalNumber(raw.durationFrames, `${name}.durationFrames`, 1);
  const timing = {...common, ...(offsetFrames === undefined ? {} : {offsetFrames}), ...(durationFrames === undefined ? {} : {durationFrames})};
  if (type === 'reveal') {
    noUnknown(raw, ['type', 'beatId', 'offsetFrames', 'durationFrames', 'fromScale'], name);
    const fromScale = optionalNumber(raw.fromScale, `${name}.fromScale`, 0);
    return {...timing, type, ...(fromScale === undefined ? {} : {fromScale})};
  }
  if (type === 'draw') {noUnknown(raw, ['type', 'beatId', 'offsetFrames', 'durationFrames'], name); return {...timing, type};}
  if (type === 'move') {
    noUnknown(raw, ['type', 'beatId', 'offsetFrames', 'durationFrames', 'from', 'to'], name);
    return {...timing, type, from: point(raw.from, `${name}.from`), to: point(raw.to, `${name}.to`)};
  }
  if (type === 'highlight' || type === 'trace') {
    noUnknown(raw, ['type', 'beatId', 'offsetFrames', 'durationFrames', 'color'], name);
    const color = raw.color === undefined ? undefined : paint(raw.color, `${name}.color`);
    return {...timing, type, ...(color === undefined ? {} : {color})};
  }
  noUnknown(raw, ['type', 'beatId', 'offsetFrames', 'durationFrames', 'from', 'to'], name);
  return {...timing, type, from: transform(raw.from, `${name}.from`), to: transform(raw.to, `${name}.to`)};
}

function primitive(value: unknown, name: string, ids: Set<string>): VisualPrimitive {
  const raw = object(value, name);
  const id = text(raw.id, `${name}.id`);
  if (ids.has(id)) throw new Error(`Duplicate primitive id ${id}`);
  ids.add(id);
  const type = choice(raw.type, ['rect', 'circle', 'ellipse', 'polygon', 'path', 'arrow', 'text', 'group'], `${name}.type`);
  const parsedStyle = style(raw.style, `${name}.style`);
  const actions = raw.actions === undefined ? undefined : array(raw.actions, `${name}.actions`).map((item, index) => action(item, `${name}.actions[${index}]`));
  const base = {id, ...(parsedStyle === undefined ? {} : {style: parsedStyle}), ...(actions === undefined ? {} : {actions})};
  if (type === 'rect') {
    noUnknown(raw, ['id', 'type', 'style', 'actions', 'x', 'y', 'width', 'height', 'rx'], name);
    const rx = optionalNumber(raw.rx, `${name}.rx`, 0);
    return {...base, type, x: number(raw.x, `${name}.x`), y: number(raw.y, `${name}.y`), width: number(raw.width, `${name}.width`, 0), height: number(raw.height, `${name}.height`, 0), ...(rx === undefined ? {} : {rx})};
  }
  if (type === 'circle') {noUnknown(raw, ['id', 'type', 'style', 'actions', 'cx', 'cy', 'r'], name); return {...base, type, cx: number(raw.cx, `${name}.cx`), cy: number(raw.cy, `${name}.cy`), r: number(raw.r, `${name}.r`, 0)};}
  if (type === 'ellipse') {noUnknown(raw, ['id', 'type', 'style', 'actions', 'cx', 'cy', 'rx', 'ry'], name); return {...base, type, cx: number(raw.cx, `${name}.cx`), cy: number(raw.cy, `${name}.cy`), rx: number(raw.rx, `${name}.rx`, 0), ry: number(raw.ry, `${name}.ry`, 0)};}
  if (type === 'polygon') {noUnknown(raw, ['id', 'type', 'style', 'actions', 'points'], name); return {...base, type, points: array(raw.points, `${name}.points`).map((item, index) => point(item, `${name}.points[${index}]`))};}
  if (type === 'path') {noUnknown(raw, ['id', 'type', 'style', 'actions', 'd', 'pathLength'], name); const pathLength = optionalNumber(raw.pathLength, `${name}.pathLength`, 0); return {...base, type, d: text(raw.d, `${name}.d`), ...(pathLength === undefined ? {} : {pathLength})};}
  if (type === 'arrow') {noUnknown(raw, ['id', 'type', 'style', 'actions', 'from', 'to', 'bend', 'marker'], name); const bend = optionalNumber(raw.bend, `${name}.bend`); const marker = raw.marker === undefined ? undefined : choice(raw.marker, ['arrow', 'dot', 'none'], `${name}.marker`); return {...base, type, from: point(raw.from, `${name}.from`), to: point(raw.to, `${name}.to`), ...(bend === undefined ? {} : {bend}), ...(marker === undefined ? {} : {marker})};}
  if (type === 'text') {noUnknown(raw, ['id', 'type', 'style', 'actions', 'x', 'y', 'width', 'height', 'text', 'align', 'fontSize', 'fontWeight'], name); const align = raw.align === undefined ? undefined : choice(raw.align, ['start', 'middle', 'end'], `${name}.align`); const fontSize = optionalNumber(raw.fontSize, `${name}.fontSize`, 1); const fontWeight = raw.fontWeight === undefined ? undefined : choice(String(raw.fontWeight), ['400', '500', '600'], `${name}.fontWeight`); return {...base, type, x: number(raw.x, `${name}.x`), y: number(raw.y, `${name}.y`), width: number(raw.width, `${name}.width`, 0), height: number(raw.height, `${name}.height`, 0), text: text(raw.text, `${name}.text`), ...(align === undefined ? {} : {align}), ...(fontSize === undefined ? {} : {fontSize}), ...(fontWeight === undefined ? {} : {fontWeight: Number(fontWeight) as 400 | 500 | 600})};}
  noUnknown(raw, ['id', 'type', 'style', 'actions', 'transform', 'children'], name);
  const transform = raw.transform === undefined ? undefined : text(raw.transform, `${name}.transform`);
  if (transform && !/^(?:(?:translate|scale|rotate|matrix|skewX|skewY)\s*\([-+.,\d\seE]+\)\s*)+$/.test(transform)) throw new Error(`${name}.transform is not a safe SVG transform`);
  return {...base, type, ...(transform === undefined ? {} : {transform}), children: array(raw.children, `${name}.children`).map((item, index) => primitive(item, `${name}.children[${index}]`, ids))};
}

/** Strict inert-data boundary. Unknown fields and malformed primitives are rejected. */
export function parseRenderVisualSpec(value: unknown): RenderVisualSpec {
  const raw = object(value, 'visualSpec');
  noUnknown(raw, ['version', 'id', 'language', 'width', 'height', 'layout', 'primitives', 'background', 'code'], 'visualSpec');
  if (raw.version !== 1 || raw.width !== 1280 || raw.height !== 720) throw new Error('VisualSpec must be version 1 at 1280×720');
  const language = choice(raw.language, languages, 'visualSpec.language') as Language;
  const ids = new Set<string>();
  const result: RenderVisualSpec = {version: 1, id: text(raw.id, 'visualSpec.id'), language, width: 1280, height: 720,
    layout: choice(raw.layout, layouts, 'visualSpec.layout'), primitives: array(raw.primitives, 'visualSpec.primitives').map((item, index) => primitive(item, `visualSpec.primitives[${index}]`, ids))};
  if (raw.background !== undefined) result.background = paint(raw.background, 'visualSpec.background');
  if (raw.code !== undefined) {
    const code = object(raw.code, 'visualSpec.code'); noUnknown(code, ['source', 'language', 'activeLines'], 'visualSpec.code');
    const activeLines = object(code.activeLines, 'visualSpec.code.activeLines');
    result.code = {source: text(code.source, 'visualSpec.code.source'), language: choice(code.language, codeLanguages, 'visualSpec.code.language'), activeLines: Object.fromEntries(Object.entries(activeLines).map(([beat, lines]) => [beat, array(lines, `activeLines.${beat}`).map((line, index) => Math.trunc(number(line, `activeLines.${beat}[${index}]`, 1))) ]))};
  }
  return result;
}

