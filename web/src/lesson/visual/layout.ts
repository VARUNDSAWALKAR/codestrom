import {theme} from '../theme';
import type {Point, VisualPrimitive} from './types';

export interface LayoutItem {id: string; label: string; note?: string}
export interface NetworkEdge {from: string; to: string; label?: string; directed?: boolean}
const reveal = (beatId: string) => [{type: 'reveal' as const, beatId}];
const label = (item: LayoutItem, x: number, y: number, width: number, beatId: string): VisualPrimitive[] => [
  {id: `${item.id}-box`, type: 'rect', x, y, width, height: 92, rx: theme.boxRadius,
    style: {fill: theme.surface, stroke: theme.line, strokeWidth: 2}, actions: reveal(beatId)},
  {id: `${item.id}-label`, type: 'text', x: x + 16, y: y + 14, width: width - 32, height: 64,
    text: item.label, align: 'middle', fontSize: 27, fontWeight: 600, actions: reveal(beatId)},
];

export function flowLayout(items: LayoutItem[], beatIds: string[]): VisualPrimitive[] {
  if (items.length < 2 || items.length > 6 || beatIds.length !== items.length) throw new Error('Flow layout requires 2–6 matching items and beats');
  const width = Math.min(250, (1120 - (items.length - 1) * 42) / items.length);
  const start = (1280 - (items.length * width + (items.length - 1) * 42)) / 2;
  return items.flatMap((item, index) => {
    const x = start + index * (width + 42);
    const primitives = label(item, x, 305, width, beatIds[index] ?? '');
    if (index > 0) primitives.unshift({id: `${item.id}-edge`, type: 'arrow', from: {x: x - 42, y: 351}, to: {x, y: 351}, marker: 'arrow', style: {stroke: theme.accent, strokeWidth: 3}, actions: [{type: 'draw', beatId: beatIds[index] ?? ''}]});
    return primitives;
  });
}

export function gridLayout(items: LayoutItem[], columns: number, beatIds: string[]): VisualPrimitive[] {
  if (!Number.isInteger(columns) || columns < 1 || items.length < 1 || beatIds.length !== items.length) throw new Error('Invalid grid layout');
  const cellWidth = Math.min(240, (1080 - (columns - 1) * 24) / columns);
  const rows = Math.ceil(items.length / columns); const totalWidth = columns * cellWidth + (columns - 1) * 24;
  return items.flatMap((item, index) => label(item, (1280 - totalWidth) / 2 + (index % columns) * (cellWidth + 24),
    185 + Math.floor(index / columns) * Math.min(130, 330 / rows), cellWidth, beatIds[index] ?? ''));
}

export function comparisonLayout(left: LayoutItem[], right: LayoutItem[], beatIds: string[]): VisualPrimitive[] {
  const all = [...left, ...right]; if (beatIds.length !== all.length) throw new Error('Comparison beats must match items');
  return all.flatMap((item, index) => {
    const sideIndex = index < left.length ? index : index - left.length;
    const x = index < left.length ? 110 : 690; const y = 180 + sideIndex * 112;
    return label(item, x, y, 480, beatIds[index] ?? '');
  });
}

export function networkLayout(items: LayoutItem[], edges: NetworkEdge[], beatIds: string[]): VisualPrimitive[] {
  if (items.length < 2 || beatIds.length !== items.length) throw new Error('Network nodes and beats must match');
  const positions = new Map<string, Point>(items.map((item, index) => [item.id, {x: 640 + 360 * Math.cos(-Math.PI / 2 + index * 2 * Math.PI / items.length), y: 350 + 185 * Math.sin(-Math.PI / 2 + index * 2 * Math.PI / items.length)}]));
  const links: VisualPrimitive[] = edges.map((edge, index) => {
    const from = positions.get(edge.from); const to = positions.get(edge.to); if (!from || !to) throw new Error('Network edge references an unknown node');
    return {id: `edge-${index}`, type: 'arrow', from, to, marker: edge.directed === false ? 'none' : 'arrow', style: {stroke: theme.line, strokeWidth: 3}, actions: [{type: 'draw', beatId: beatIds[Math.max(0, items.findIndex((item) => item.id === edge.to))] ?? ''}]};
  });
  const nodes = items.flatMap((item, index) => {
    const position = positions.get(item.id); if (!position) return [];
    return [{id: `${item.id}-node`, type: 'circle' as const, cx: position.x, cy: position.y, r: 54, style: {fill: theme.surface, stroke: theme.accent, strokeWidth: 3}, actions: reveal(beatIds[index] ?? '')},
      {id: `${item.id}-label`, type: 'text' as const, x: position.x - 48, y: position.y - 28, width: 96, height: 56, text: item.label, align: 'middle' as const, fontSize: 22, fontWeight: 600 as const, actions: reveal(beatIds[index] ?? '')}];
  });
  return [...links, ...nodes];
}

export function coordinateLayout(xLabel: string, yLabel: string, points: Array<{id: string; x: number; y: number; label: string; beatId: string}>): VisualPrimitive[] {
  const origin = {x: 640, y: 360}; const scale = 48;
  return [
    {id: 'x-axis', type: 'arrow', from: {x: 160, y: origin.y}, to: {x: 1120, y: origin.y}, style: {stroke: theme.ink2, strokeWidth: 2}},
    {id: 'y-axis', type: 'arrow', from: {x: origin.x, y: 550}, to: {x: origin.x, y: 145}, style: {stroke: theme.ink2, strokeWidth: 2}},
    {id: 'x-label', type: 'text', x: 1080, y: 372, width: 80, height: 40, text: xLabel, align: 'middle', fontSize: 20},
    {id: 'y-label', type: 'text', x: 650, y: 125, width: 100, height: 40, text: yLabel, fontSize: 20},
    ...points.flatMap((point) => [{id: point.id, type: 'circle' as const, cx: origin.x + point.x * scale, cy: origin.y - point.y * scale, r: 8, style: {fill: theme.accent}, actions: reveal(point.beatId)},
      {id: `${point.id}-label`, type: 'text' as const, x: origin.x + point.x * scale + 12, y: origin.y - point.y * scale - 24, width: 120, height: 40, text: point.label, fontSize: 19, actions: reveal(point.beatId)}])
  ];
}

