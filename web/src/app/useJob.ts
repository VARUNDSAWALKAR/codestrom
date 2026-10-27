import {useEffect, useState} from 'react';
import {getJob, getLesson, wait, type Job, type LessonResponse} from './api';

export function useJob(jobId: string | undefined, retry: number) {
  const [job, setJob] = useState<Job | null>(null);
  const [lesson, setLesson] = useState<LessonResponse | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    setJob(null); setLesson(null); setError('');
    if (!jobId) return;
    const controller = new AbortController();
    const {signal} = controller;
    void (async () => {
      let opened = false;
      const deadline = performance.now() + 12 * 60 * 1000;
      while (!signal.aborted && performance.now() < deadline) {
        const current = await getJob(jobId, signal);
        if (signal.aborted) return;
        setJob(current);
        if (current.playable && (!opened || current.status === 'done' || current.status === 'error')) {
          const response = await getLesson(current.lesson_id, current.variant, signal);
          if (signal.aborted) return;
          setLesson(response); opened = true;
        }
        if (current.status === 'error') throw new Error(current.error ?? 'The lesson job failed.');
        if (current.status === 'done') {
          if (!current.playable) throw new Error('The job finished without a playable lesson.');
          return;
        }
        await wait(500, signal);
      }
      if (!signal.aborted) throw new Error('Generation is taking longer than expected. Retry to check the existing job; no new lesson will be submitted.');
    })().catch((reason: unknown) => {
      if (!signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not check the lesson job.');
    });
    return () => controller.abort();
  }, [jobId, retry]);
  return {job, lesson, error};
}
