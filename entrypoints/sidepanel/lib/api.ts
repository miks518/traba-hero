import type { ApiScanResponse, ResumeData, RiskScoreBreakdown, ScannedJob, VerificationResult } from '../types';

const API_BASE = import.meta.env.WXT_API_BASE;
const CLIENT_KEY = import.meta.env.WXT_CLIENT_KEY;

async function authHeaders(): Promise<Record<string, string>> {
  return { 'X-Trabahero-Client-Key': CLIENT_KEY ?? '' };
}

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

export async function pingHealth(externalSignal?: AbortSignal): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3000);

  if (externalSignal) {
    externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const res = await fetch(`${API_BASE}/health`, {
      method: 'GET',
      headers: await authHeaders(),
      signal: controller.signal,
    });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
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
      headers: { ...await authHeaders(), ...(body ? { 'Content-Type': 'application/json' } : {}) },
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
  imagesBase64: string[],
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
      headers: { 'Content-Type': 'application/json', ...await authHeaders() },
      body: JSON.stringify({ images_base64: imagesBase64 }),
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
      headers: { 'Content-Type': 'application/json', ...await authHeaders() },
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

export interface ResumeStreamResult {
  data?: ResumeData;
  timedOut?: boolean;
}

export async function analyzeResumeStream(
  fileBase64: string,
  fileType: string,
  externalSignal: AbortSignal,
  onProgress: (progress: ScanProgress) => void,
  timeoutMs = 300000,
): Promise<ResumeStreamResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  if (externalSignal) {
    externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const res = await fetch(`${API_BASE}/api/analyze-resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...await authHeaders() },
      body: JSON.stringify({ file_base64: fileBase64, file_type: fileType }),
      signal: controller.signal,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new ApiRequestError(res.status, text || res.statusText);
    }

    const data = await consumeSseStreamResume(res.body, onProgress);
    return { data: data ?? undefined };
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

async function consumeSseStreamResume(
  body: ReadableStream<Uint8Array> | null,
  onProgress: (progress: ScanProgress) => void,
): Promise<ResumeData | null> {
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
        return event.data as ResumeData;
      } else if (event.type === 'error') {
        throw new Error(String(event.error ?? 'Resume analysis failed'));
      }
    }
  }
  return null;
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

export interface MatchStreamResult {
  data?: { matches: { job_id: string; score: number; label: string; skill_gaps: string[]; matched_skills: string[]; reasoning: string; experience_fit: string; industry_fit: string; recommended_actions: string[] }[] };
  timedOut?: boolean;
}

export async function matchResumeToJobsStream(
  resume: ResumeData,
  jobs: ScannedJob[],
  externalSignal: AbortSignal,
  onProgress: (progress: ScanProgress) => void,
  timeoutMs = 300000,
): Promise<MatchStreamResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  if (externalSignal) {
    externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const res = await fetch(`${API_BASE}/api/match-resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...await authHeaders() },
      body: JSON.stringify({
        resume,
        jobs: jobs.map(j => ({ id: j.id, title: j.title, summary: j.summary })),
      }),
      signal: controller.signal,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new ApiRequestError(res.status, text || res.statusText);
    }

    const data = await consumeSseStreamMatch(res.body, onProgress);
    return { data: data ?? undefined };
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

async function consumeSseStreamMatch(
  body: ReadableStream<Uint8Array> | null,
  onProgress: (progress: ScanProgress) => void,
): Promise<MatchStreamResult['data'] | null> {
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
          stage: String(event.stage ?? 'Matching'),
        });
      } else if (event.type === 'result') {
        return event.data as MatchStreamResult['data'];
      } else if (event.type === 'error') {
        throw new Error(String(event.error ?? 'Match failed'));
      }
    }
  }
  return null;
}

export interface OfferAnalysis {
  kind: string;
  verdict: string;
  what_it_asks: string;
  what_it_offers: string;
  what_to_check: string;
  is_offer: boolean;
}

export interface OfferStreamResult {
  data?: OfferAnalysis;
  timedOut?: boolean;
}

/**
 * Post-only analysis. Used when a posting names no employer, so external
 * verification cannot run. Assesses the offer on its own terms and returns a
 * verdict, so the user is never left without one.
 */
export async function analyzeOfferStream(
  text: string,
  companyName: string,
  externalSignal: AbortSignal,
  onProgress: (progress: ScanProgress) => void,
  timeoutMs = 90000,
): Promise<OfferStreamResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  if (externalSignal) {
    externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const res = await fetch(`${API_BASE}/api/analyze-offer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...await authHeaders() },
      body: JSON.stringify({ text, company_name: companyName }),
      signal: controller.signal,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new ApiRequestError(res.status, text || res.statusText);
    }

    const data = await consumeSseStreamOffer(res.body, onProgress);
    return { data: data ?? undefined };
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

async function consumeSseStreamOffer(
  body: ReadableStream<Uint8Array> | null,
  onProgress: (progress: ScanProgress) => void,
): Promise<OfferAnalysis | null> {
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
          stage: String(event.stage ?? 'Reading the offer'),
        });
      } else if (event.type === 'result') {
        return event.data as OfferAnalysis;
      } else if (event.type === 'error') {
        throw new Error(String(event.error ?? 'Analysis failed'));
      }
    }
  }
  return null;
}

export interface VerifyStreamResult {
  result?: VerificationResult & { riskScore?: number; riskLevel?: string; scoreBreakdown?: RiskScoreBreakdown };
  timedOut?: boolean;
}

export async function verifyJobStream(
  context: { company_name: string; job_summary: string; red_flags?: { flag: string; reasoning: string; severity: string }[] },
  externalSignal: AbortSignal,
  onProgress: (progress: ScanProgress) => void,
  onSearch: (query: string, round: number) => void,
  timeoutMs = 120000,
): Promise<VerifyStreamResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  if (externalSignal) {
    externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const res = await fetch(`${API_BASE}/api/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...await authHeaders() },
      body: JSON.stringify(context),
      signal: controller.signal,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new ApiRequestError(res.status, text || res.statusText);
    }

    const body = res.body;
    if (!body) return { timedOut: true };

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
            stage: String(event.stage ?? 'Verifying'),
          });
        } else if (event.type === 'search') {
          onSearch(String(event.query ?? ''), Number(event.round ?? 0));
        } else if (event.type === 'result') {
          const data = event.data as {
            items: VerificationResult['items'];
            report: string;
            recommendation: string;
            riskScore?: number;
            riskLevel?: string;
            scoreBreakdown?: RiskScoreBreakdown;
            search_log: unknown[];
            no_company_name?: boolean;
          };
          return {
            result: {
              items: data.items ?? [],
              report: data.report ?? '',
              recommendation: data.recommendation ?? '',
              riskScore: data.riskScore,
              riskLevel: data.riskLevel as 'low' | 'moderate' | 'high' | 'critical' | undefined,
              scoreBreakdown: data.scoreBreakdown,
              searchLog: data.search_log as VerificationResult['searchLog'],
              noCompanyName: Boolean(data.no_company_name),
            },
          };
        } else if (event.type === 'error') {
          throw new Error(String(event.error ?? 'Verification failed'));
        }
      }
    }
    return {};
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
