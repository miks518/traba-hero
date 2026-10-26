import type { AnomalyAssessment, ApiScanResponse, ResumeData, ScannedJob, VerificationResult } from '../types';

const API_BASE = import.meta.env.WXT_API_BASE;

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
      headers: {},
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
      headers: { ...(body ? { 'Content-Type': 'application/json' } : {}) },
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
        const data = event.data as ApiScanResponse;
        // The wire now carries the verdict vocabulary directly.
        return { ...data };
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
      headers: { 'Content-Type': 'application/json',  },
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
      headers: { 'Content-Type': 'application/json',  },
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
      headers: { 'Content-Type': 'application/json',  },
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
      headers: { 'Content-Type': 'application/json',  },
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
  verdict_level?: 'clear' | 'note' | 'caution' | 'stop' | null;
  verdictBreakdown?: Record<string, unknown>;
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
  anomalies: unknown[] = [],
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
      headers: { 'Content-Type': 'application/json',  },
      body: JSON.stringify({ text, company_name: companyName, anomalies }),
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

/**
 * What `/api/verify` is asked about.
 *
 * `attributes` is the posting's own stated details, forwarded verbatim from the
 * scan response. The backend quotes it back to the model as the claims its
 * categories test, so dropping it here is not a local loss: `Channel Match` —
 * the one check that can detect an impersonation — would have nothing to
 * reason about.
 *
 * `search_queries` are the searches the scan model proposed, capped at 2. They
 * are issued alongside the one query the backend builds from the employer name.
 * Dropping them leaves every verification running on a single query, reported
 * as an ordinary lookup with no error anywhere — which is how the previous
 * version of this feature failed.
 */
export interface VerifyContext {
  company_name: string;
  job_summary: string;
  /**
   * The findings the verify stage assesses. `code` and `quote` are forwarded so
   * the prompt can show the model the scan's own rule and the posting's words,
   * not just a paraphrase. They are optional because a scan from before either
   * field existed still has findings worth checking.
   */
  anomalies?: {
    flag: string;
    reasoning: string;
    severity: string;
    code?: string;
    quote?: string;
  }[];
  attributes?: Record<string, string>;
  search_queries?: string[];
}

export interface VerifyStreamResult {
  result?: VerificationResult & { verdict?: string; verdictBreakdown?: Record<string, unknown>; verdictText?: string };
  timedOut?: boolean;
}

export interface WireAnomalyAssessment {
  index?: number;
  status?: string;
  finding?: string;
  source_title?: string;
  source_url?: string;
}

/**
 * The verify wire's assessment list, in the client's shape.
 *
 * `undefined` means the key was absent, which the panel reads as "this reading
 * predates the check". `[]` means the key was present and empty, which means the
 * check ran and produced no verdict. Those two produce different amber notes, so
 * the distinction is preserved rather than defaulted away.
 *
 * A status outside the closed set degrades to `unknown`. The backend already
 * maps one, but a client that trusted the string would pass an unknown value to
 * the card's lookup and render no strip at all — a silent gap where a finding
 * should be. `unknown` is the honest square: we could not settle it.
 */
export function mapAnomalyAssessments(
  raw: WireAnomalyAssessment[] | undefined,
): AnomalyAssessment[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  return raw
    .filter(
      (assessment): assessment is WireAnomalyAssessment =>
        Boolean(assessment) && typeof assessment === 'object',
    )
    .map((assessment): AnomalyAssessment => ({
      index: Number.isInteger(assessment.index) ? assessment.index : undefined,
      status:
        assessment.status === 'stale' || assessment.status === 'contradicted'
          ? assessment.status
          : 'unknown',
      finding: assessment.finding ?? '',
      sourceTitle: assessment.source_title || undefined,
      sourceUrl: assessment.source_url || undefined,
    }));
}

export async function verifyJobStream(
  context: VerifyContext,
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
      headers: { 'Content-Type': 'application/json',  },
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
            evidence?: VerificationResult['evidence'];
            report: string;
            recommendation: string;
            verdict?: string;
            verdictBreakdown?: Record<string, unknown>;
            verdictText?: string;
            requestClass?: string;
            request_class?: string;
            no_company_name?: boolean;
            search_ok?: boolean;
            search_error?: string;
            search_count?: number;
            search_partial?: boolean;
            queries_issued?: number;
            queries_failed?: number;
            model_queries?: string[];
            debug_search_raw?: Array<{ query: string; raw: string }>;
            anomaly_assessments?: Array<{
              index: number;
              status: string;
              finding: string;
              source_title?: string;
              source_url?: string;
            }>;
            /**
             * camelCase here while its neighbours stay snake_case, because
             * `verification_flow.py` puts it in its response dict that way and the
             * rest of that dict is untouched legacy. Read both spellings so the
             * client does not depend on which one the backend happened to keep.
             */
            verdictReason?: string;
          };
          return {
            result: {
              items: data.items ?? [],
              evidence: data.evidence ?? [],
              report: data.report ?? '',
              recommendation: data.recommendation ?? '',
              // Empty string rather than dropped: the backend already screens
              // what may appear here, and an absent value is what the panel reads
              // as "no reason to show".
              verdictReason: data.verdictReason ?? '',
              verdict: data.verdict as 'clear' | 'note' | 'caution' | 'stop' | undefined,
              verdictBreakdown: data.verdictBreakdown,
              verdictText: data.verdictText,
              requestClass: data.requestClass ?? data.request_class,
              searchOk: data.search_ok,
              searchError: data.search_error,
              searchPartial: data.search_partial,
              queriesIssued: data.queries_issued,
              queriesFailed: data.queries_failed,
              modelQueries: data.model_queries,
              debugSearchRaw: data.debug_search_raw,
              anomalyAssessments: mapAnomalyAssessments(data.anomaly_assessments),
              anomalyAssessmentRun: Array.isArray(data.anomaly_assessments),
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
