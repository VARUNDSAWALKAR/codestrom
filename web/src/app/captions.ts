import type {Timeline} from '../lesson/types';

export function timelineSrt(timeline: Timeline): string {
  const timestamp = (frame: number) => {
    const ms = Math.round(frame / timeline.fps * 1000);
    const pad = (n: number, width = 2) => String(n).padStart(width, '0');
    return `${pad(Math.floor(ms / 3600000))}:${pad(Math.floor(ms / 60000) % 60)}:${pad(Math.floor(ms / 1000) % 60)},${pad(ms % 1000, 3)}`;
  };
  return timeline.scenes.flatMap((scene) => scene.beats.flatMap((beat) => beat.captions))
    .map((caption, index) => `${index + 1}\n${timestamp(caption.start_frame)} --> ${timestamp(caption.end_frame)}\n${caption.text}\n`).join('\n');
}
