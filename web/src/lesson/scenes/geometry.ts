import type {DiagramScene} from '../types';

export interface Box {x: number; y: number; width: number; height: number}
export interface Connector {from: number; to: number; reveal: number; path: string}
const point = (x: number, y: number) => `${x},${y}`;

export function diagramGeometry(layout: DiagramScene['layout'], count: number): {boxes: Box[]; connectors: Connector[]} {
  if (count < 2 || count > 6) throw new Error('Diagram requires 2–6 steps');
  let boxes: Box[];
  if (layout === 'flow') {
    const width = Math.min(240, (1152 - (Math.min(count, 3) - 1) * 72) / Math.min(count, 3));
    boxes = Array.from({length: count}, (_, index) => {
      const rowSize = count <= 4 ? count : index < 3 ? 3 : count - 3;
      const w = count <= 4 ? Math.min(240, (1152 - (count - 1) * 72) / count) : width;
      const slot = count <= 4 ? index : index % 3;
      return {x: (1280 - (rowSize * w + (rowSize - 1) * 72)) / 2 + slot * (w + 72) + w / 2,
        y: count <= 4 ? 330 : index < 3 ? 230 : 450, width: w, height: 112};
    });
  } else if (layout === 'cycle') {
    boxes = Array.from({length: count}, (_, index) => {
      const angle = -Math.PI / 2 + index * 2 * Math.PI / count;
      return {x: 640 + 380 * Math.cos(angle), y: 350 + 170 * Math.sin(angle), width: 200, height: 84};
    });
  } else {
    const slots: Record<number, [number, number][]> = {
      2: [[240, 350], [1040, 350]],
      3: [[240, 350], [1040, 210], [1040, 490]],
      4: [[240, 210], [1040, 210], [240, 490], [1040, 490]],
      5: [[240, 210], [1040, 210], [240, 490], [1040, 490], [640, 540]],
      6: [[240, 210], [1040, 210], [240, 490], [1040, 490], [240, 350], [1040, 350]],
    };
    boxes = (slots[count] ?? []).map(([x, y]) => ({x, y, width: 280, height: 80}));
  }
  const connectors: Connector[] = [];
  for (let index = 0; index < count; index++) {
    const target = boxes[index];
    if (!target) continue;
    if (layout === 'labelled') {
      const center = {x: 640, y: 350, width: 260, height: 96};
      const start = edge(center, target.x - center.x, target.y - center.y);
      const end = edge(target, center.x - target.x, center.y - target.y);
      connectors.push({from: -1, to: index, reveal: index, path: `M ${point(...start)} L ${point(...end)}`});
    } else if (layout === 'flow' && index > 0) {
      const source = boxes[index - 1];
      if (!source) continue;
      const acrossRows = source.y !== target.y;
      const start = [source.x + source.width / 2, source.y];
      const end = acrossRows ? [target.x, target.y - target.height / 2] : [target.x - target.width / 2, target.y];
      const path = acrossRows ? `M ${start.join(',')} H ${source.x + source.width / 2 + 40} V 340 H ${target.x} V ${end[1]}` : `M ${start.join(',')} L ${end.join(',')}`;
      connectors.push({from: index - 1, to: index, reveal: index, path});
    } else if (layout === 'cycle') {
      const nextIndex = (index + 1) % count;
      const next = boxes[nextIndex];
      if (!next) continue;
      const a = -Math.PI / 2 + index * 2 * Math.PI / count;
      const b = a + 2 * Math.PI / count;
      const tangentA = [-380 * Math.sin(a), 170 * Math.cos(a)];
      const tangentB = [-380 * Math.sin(b), 170 * Math.cos(b)];
      const start = edge(target, tangentA[0] ?? 0, tangentA[1] ?? 0);
      const end = edge(next, -(tangentB[0] ?? 0), -(tangentB[1] ?? 0));
      const tangentLength = Math.hypot(...tangentB);
      // Stop before the box border so the arrowhead stays visible.
      end[0] -= (tangentB[0] ?? 0) / tangentLength * 6;
      end[1] -= (tangentB[1] ?? 0) / tangentLength * 6;
      const strength = count === 2 ? 1.2 : 0.35;
      const c1 = [start[0] + (tangentA[0] ?? 0) * strength, start[1] + (tangentA[1] ?? 0) * strength];
      const c2 = [end[0] - (tangentB[0] ?? 0) * strength, end[1] - (tangentB[1] ?? 0) * strength];
      connectors.push({from: index, to: nextIndex, reveal: nextIndex === 0 ? count - 1 : nextIndex,
        path: `M ${point(...start)} C ${c1.join(',')} ${c2.join(',')} ${point(...end)}`});
    }
  }
  return {boxes, connectors};
}

function edge(box: Box, dx: number, dy: number): [number, number] {
  const scale = Math.min(dx === 0 ? Infinity : box.width / 2 / Math.abs(dx),
    dy === 0 ? Infinity : box.height / 2 / Math.abs(dy));
  return [box.x + dx * scale, box.y + dy * scale];
}
