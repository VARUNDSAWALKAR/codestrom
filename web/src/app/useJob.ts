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
      let lastExportStatus: Job['export_status'] | null = null;
      const deadline = performance.now() + 12 * 60 * 1000;
      while (!signal.aborted && performance.now() < deadline) {
        const current = await getJob(jobId, signal);
        if (signal.aborted) return;
        setJob(current);
        const exportFinished = current.export_status === 'completed' || current.export_status === 'failed' || current.export_status === 'skipped';
        if (current.preview_ready && (!opened || (exportFinished && current.export_status !== lastExportStatus))) {
          const response = await getLesson(current.lesson_id, current.variant, signal);
          if (signal.aborted) return;
          setLesson(response); opened = true; lastExportStatus = current.export_status;
        }
        if (current.status === 'error' && !(current.preview_ready && current.export_status === 'failed')) {
          const detail = current.error_detail;
          throw new Error(detail ? `Failed during ${detail.stage}: ${detail.message}` : current.error ?? 'The lesson job failed.');
        }
        if (exportFinished && current.preview_ready) return;
        if (current.status === 'done') {
          if (!current.preview_ready) throw new Error('The job finished without a playable lesson.');
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
