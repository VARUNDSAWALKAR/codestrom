import type {LessonResponse} from './api';
import {localMediaPath} from '../lesson/validate';

export type LessonCategory = 'Programming' | 'Science' | 'Mathematics' | 'Other';
export interface LibraryLesson {
  id: string;
  variant: string;
  title: string;
  language: string;
  seconds: number;
  scenes: number | null;
  category: LessonCategory;
  createdAt: string | null;
  openedAt: string | null;
  mp4: string | null;
}
const key = 'blu.lesson-history.v1';
let memory: LibraryLesson[] = [];

export function lessonCategory(title: string): LessonCategory {
  if (/python|code|program|algorithm|binary search|loop|javascript|function|array/i.test(title)) return 'Programming';
  if (/newton|force|water|cycle|photosynth|physics|chemistry|biology|atom|planet|gravity/i.test(title)) return 'Science';
  if (/math|algebra|equation|fraction|geometry|calculus|probability|number|theorem/i.test(title)) return 'Mathematics';
  return 'Other';
}
function validEntry(value: unknown): value is LibraryLesson {
  if (!value || typeof value !== 'object') return false;
  const entry = value as Partial<LibraryLesson>;
  if (typeof entry.id !== 'string' || !entry.id || typeof entry.variant !== 'string' || !entry.variant ||
    typeof entry.title !== 'string' || typeof entry.language !== 'string' ||
    typeof entry.seconds !== 'number' || !Number.isFinite(entry.seconds) || entry.seconds <= 0 ||
    !(entry.scenes === null || (Number.isInteger(entry.scenes) && Number(entry.scenes) > 0)) ||
    !['Programming', 'Science', 'Mathematics', 'Other'].includes(String(entry.category))) return false;
  for (const date of [entry.createdAt, entry.openedAt]) if (date !== null && (typeof date !== 'string' || !Number.isFinite(Date.parse(date)))) return false;
  if (entry.mp4 !== null) {
    if (typeof entry.mp4 !== 'string') return false;
    try {localMediaPath(entry.mp4);} catch {return false;}
  }
  return true;
}
export function readHistory(): {lessons: LibraryLesson[]; persistent: boolean} {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? '[]');
    if (Array.isArray(value)) memory = value.filter(validEntry).slice(0, 100);
    return {lessons: memory, persistent: true};
  } catch {return {lessons: memory, persistent: false};}
}
export function rememberLesson(response: LessonResponse): void {
  const entry: LibraryLesson = {
    id: response.lesson_id, variant: response.variant, title: response.lesson.title,
    language: response.lesson.language, seconds: response.timeline.duration_frames / response.timeline.fps,
    scenes: response.lesson.scenes.length, category: lessonCategory(`${response.lesson.title} ${response.lesson.topic}`),
    createdAt: null, openedAt: new Date().toISOString(), mp4: response.media.mp4,
  };
  if (!validEntry(entry)) return;
  memory = [entry, ...readHistory().lessons.filter((item) => item.id !== entry.id || item.variant !== entry.variant)].slice(0, 100);
  try {localStorage.setItem(key, JSON.stringify(memory));} catch { /* Keep this session's history if storage is unavailable. */ }
}

/** Optional library endpoint from api-contracts.md §8; history remains useful on older backends. */
export async function fetchLibrary(signal: AbortSignal): Promise<LibraryLesson[]> {
  const response = await fetch('/api/lessons', {headers: {Accept: 'application/json'}, signal: AbortSignal.any([signal, AbortSignal.timeout(10000)])});
  if (!response.ok) throw new Error('The local lesson library is unavailable.');
  const body: unknown = await response.json();
  if (!body || typeof body !== 'object' || !('lessons' in body) || !Array.isArray(body.lessons)) throw new Error('Invalid library response.');
  const lessons: LibraryLesson[] = [];
  for (const raw of body.lessons) {
    if (!raw || typeof raw !== 'object') throw new Error('Invalid library lesson.');
    const item = raw as Record<string, unknown>;
    if (typeof item.lesson_id !== 'string' || typeof item.title !== 'string' || typeof item.topic !== 'string' ||
      typeof item.created_at !== 'string' || !Array.isArray(item.variants)) throw new Error('Invalid library lesson.');
    for (const rawVariant of item.variants) {
      if (!rawVariant || typeof rawVariant !== 'object') throw new Error('Invalid library variant.');
      const variant = rawVariant as Record<string, unknown>;
      if (typeof variant.variant !== 'string' || typeof variant.has_mp4 !== 'boolean' || typeof variant.duration_s !== 'number') throw new Error('Invalid library variant.');
      const entry: LibraryLesson = {
        id: item.lesson_id, title: item.title, variant: variant.variant, language: variant.variant.split('-')[0] ?? '',
        seconds: variant.duration_s, scenes: null, category: lessonCategory(`${item.title} ${item.topic}`),
        createdAt: item.created_at, openedAt: null,
        mp4: variant.has_mp4 ? `/media/${encodeURIComponent(item.lesson_id)}/${encodeURIComponent(variant.variant)}/lesson.mp4` : null,
      };
      if (!validEntry(entry)) throw new Error('Invalid library lesson metadata.');
      lessons.push(entry);
    }
  }
  return lessons;
}

export function mergeLibrary(remote: LibraryLesson[], history: LibraryLesson[]): LibraryLesson[] {
  const combined = new Map(history.map((entry) => [`${entry.id}\u0000${entry.variant}`, entry]));
  for (const entry of remote) {
    const identity = `${entry.id}\u0000${entry.variant}`;
    const saved = combined.get(identity);
    combined.set(identity, {...entry, scenes: saved?.scenes ?? null, openedAt: saved?.openedAt ?? null});
  }
  return [...combined.values()].sort((a, b) => Date.parse(b.openedAt ?? b.createdAt ?? '') - Date.parse(a.openedAt ?? a.createdAt ?? ''));
}
