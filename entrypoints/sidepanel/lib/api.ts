import type { ApiScanResponse, ResumeData, ScannedJob } from '../types';

const API_BASE = 'http://localhost:8000';

export interface ScanProgress {
  percent: number;
  stage: string;
}

export class ApiRequestError extends Error {
  status: number;
  details: string;

  constructor(status: number, details: string) {
    super(`API request failed (${status}): ${details}`);
    this.status = status;
    this.details = details;
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  timeoutMs = 90000,
  externalSignal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  if (externalSignal) {
    externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new ApiRequestError(res.status, text || res.statusText);
    }

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Request timed out');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

async function consumeSseStream(
  body: ReadableStream<Uint8Array> | null,
  onProgress: (progress: ScanProgress) => void,
): Promise<ApiScanResponse | null> {
  if (!body) return null;
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data: ')) continue;
      let event: Record<string, unknown>;
      try {
        event = JSON.parse(trimmed.slice(6));
      } catch {
        continue;
      }
      if (event.type === 'progress') {
        onProgress({
          percent: Number(event.percent ?? 0),
          stage: String(event.stage ?? 'Analyzing'),
        });
      } else if (event.type === 'result') {
        return event.data as ApiScanResponse;
      } else if (event.type === 'error') {
        throw new Error(String(event.error ?? 'Scan failed'));
      }
    }
  }
  return null;
}

export interface ScanStreamResult {
  response?: ApiScanResponse;
  timedOut?: boolean;
}

export async function scanScreenshotStream(
  imageBase64: string,
  externalSignal: AbortSignal,
  onProgress: (progress: ScanProgress) => void,
  timeoutMs = 240000,
): Promise<ScanStreamResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  if (externalSignal) {
    externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const res = await fetch(`${API_BASE}/api/scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_base64: imageBase64 }),
      signal: controller.signal,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new ApiRequestError(res.status, text || res.statusText);
    }

    const response = await consumeSseStream(res.body, onProgress);
    return { response: response ?? undefined };
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      if (externalSignal.aborted) return { timedOut: false };
      return { timedOut: true };
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function scanTextStream(
  text: string,
  externalSignal: AbortSignal,
  onProgress: (progress: ScanProgress) => void,
  timeoutMs = 240000,
): Promise<ScanStreamResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  if (externalSignal) {
    externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const res = await fetch(`${API_BASE}/api/scan-text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal: controller.signal,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new ApiRequestError(res.status, text || res.statusText);
    }

    const response = await consumeSseStream(res.body, onProgress);
    return { response: response ?? undefined };
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      if (externalSignal.aborted) return { timedOut: false };
      return { timedOut: true };
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function analyzeResume(fileBase64: string, fileType: string): Promise<ResumeData> {
  return request<ResumeData>('POST', '/api/analyze-resume', { file_base64: fileBase64, file_type: fileType }, 300000);
}

export async function matchResumeToJobs(
  resume: ResumeData,
  jobs: ScannedJob[]
): Promise<{ matches: { job_id: string; score: number; label: string; skill_gaps: string[]; matched_skills: string[]; reasoning: string; experience_fit: string; industry_fit: string; recommended_actions: string[] }[] }> {
  return request('POST', '/api/match-resume', {
    resume,
    jobs: jobs.map(j => ({ id: j.id, title: j.title, summary: j.summary })),
  }, 300000);
}
