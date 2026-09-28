import type { ScanResult, ScannedJob } from '../types';

/**
 * Replace a stored job's scan result once a later stage produces one.
 *
 * A scan is saved to history as soon as it returns, which is before external
 * verification has run. The employer stage then blends its score into the
 * posting stage's — a clean posting at 0 with a yellow-only lookup becomes
 * round(0 * 0.6 + 30 * 0.4) = 12 — and the panel shows that number while
 * history would keep showing the 0 it captured. Without this, the same posting
 * reads as two different scores in two places.
 *
 * The whole result is replaced rather than the score patched, because the stage
 * that moves the score also produces the evidence behind it: a history entry
 * showing 12 with no verification result cannot be explained by the reader.
 *
 * An unknown id is a no-op. This is called from a callback that fires after an
 * await, so the entry can legitimately be gone if history was cleared in the
 * meantime, and inventing one would resurrect a deleted job.
 */
export function updateScannedJob(
  jobs: ScannedJob[],
  id: string,
  scanResult: ScanResult,
): ScannedJob[] {
  let found = false;
  const next = jobs.map((job) => {
    if (job.id !== id) return job;
    found = true;
    return { ...job, scanResult };
  });
  return found ? next : jobs;
}

/**
 * Repairs scan history written before external verification became the only
 * source of a risk score.
 *
 * Those entries carry a synthesised `riskScore` of 80/50/10 that was derived
 * from the number of red flags, not from any measured value. Showing it as a
 * percentage would present an invented number as a finding, so it is cleared on
 * load and the job is presented as unverified until it is scanned again.
 */
export function migrateScannedJobs(stored: unknown): ScannedJob[] {
  if (!Array.isArray(stored)) return [];

  return (stored as ScannedJob[]).map((job) => {
    const scanResult = job?.scanResult;
    if (!scanResult || typeof scanResult !== 'object') return job;
    if (scanResult.riskScored === true) return job;

    return {
      ...job,
      scanResult: {
        ...scanResult,
        riskScored: false,
        riskScore: null,
        riskLevel: null,
        riskLabel: 'Not Scored',
      },
    };
  });
}
