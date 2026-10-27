import {diagramGeometry} from '../scenes/geometry';
import {theme} from '../theme';
import type {DiagramScene, Language, TimelineScene} from '../types';
import type {VisualPrimitive, VisualSpec} from './types';

/** Converts the current Lesson v1 diagram contract into the richer renderer-owned VisualSpec. */
export function diagramVisualSpec(scene: DiagramScene, timelineScene: TimelineScene, language: Language): VisualSpec {
  const geometry = diagramGeometry(scene.layout, scene.steps.length);
  const beatId = (index: number) => timelineScene.beats.find((beat) => beat.step_index === index)?.beat_id ?? `${scene.id}.step${index}`;
  const primitives: VisualPrimitive[] = geometry.connectors.map((connector, index) => ({
    id: `${scene.id}-connector-${index}`, type: 'path', d: connector.path, pathLength: 1,
    style: {fill: 'none', stroke: theme.accent, strokeWidth: 3, lineCap: 'round'},
    actions: [{type: 'draw', beatId: beatId(connector.reveal)}],
  }));
  if (scene.layout !== 'flow' && scene.center) {
    primitives.push({id: `${scene.id}-center`, type: 'group', children: [
      scene.layout === 'cycle' ? {id: `${scene.id}-center-shape`, type: 'circle', cx: 640, cy: 350, r: 70, style: {fill: theme.surface, stroke: theme.line, strokeWidth: 2}} :
        {id: `${scene.id}-center-shape`, type: 'rect', x: 510, y: 302, width: 260, height: 96, rx: theme.boxRadius, style: {fill: theme.surface, stroke: theme.line, strokeWidth: 2}},
      {id: `${scene.id}-center-text`, type: 'text', x: scene.layout === 'cycle' ? 580 : 526, y: 310,
        width: scene.layout === 'cycle' ? 120 : 228, height: 80, text: scene.center, align: 'middle', fontSize: 26, fontWeight: 600},
    ]});
  }
  geometry.boxes.forEach((box, index) => {
    const step = scene.steps[index]; if (!step) return;
    const id = `${scene.id}-step-${index}`; const idBeat = beatId(index);
    const noteY = box.y + box.height / 2 + 8; const safeNoteY = noteY + 42 > 580 ? box.y - box.height / 2 - 46 : noteY;
    const sideNote = scene.layout === 'cycle' && Math.abs(box.x - 640) > 150;
    const noteWidth = sideNote ? 140 : box.width;
    const noteX = sideNote ? box.x > 640 ? box.x - box.width / 2 - 148 : box.x + box.width / 2 + 8 : box.x - box.width / 2;
    const children: VisualPrimitive[] = [
      {id: `${id}-box`, type: 'rect', x: box.x - box.width / 2, y: box.y - box.height / 2, width: box.width, height: box.height,
        rx: theme.boxRadius, style: {fill: theme.surface, stroke: theme.line, strokeWidth: 2}, actions: [{type: 'highlight', beatId: idBeat}]},
      {id: `${id}-text`, type: 'text', x: box.x - box.width / 2 + 12, y: box.y - box.height / 2 + 8,
        width: box.width - 24, height: box.height - 16, text: step.text, align: 'middle', fontSize: 28, fontWeight: 600},
    ];
    if (step.note) children.push({id: `${id}-note`, type: 'text', x: noteX, y: sideNote ? box.y - 21 : safeNoteY,
      width: noteWidth, height: 42, text: step.note, align: 'middle', fontSize: 20, style: {fill: theme.ink2}});
    primitives.push({id, type: 'group', actions: [{type: 'reveal', beatId: idBeat, fromScale: .96}], children});
  });
  return {version: 1, id: scene.id, language, width: 1280, height: 720, layout: scene.layout === 'labelled' ? 'spatial' : 'flow', primitives};
}

