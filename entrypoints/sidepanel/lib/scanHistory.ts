import type { Anomaly, ScanResult, ScannedJob } from '../types';

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
 * Repairs stored scan history: clears invented scores and renames the field
 * that carried the posting's findings.
 *
 * **Synthesised scores.** Entries written before external verification became
 * the only source of a risk score carry an invented `riskScore` of 80/50/10,
 * derived from the number of findings rather than from any measured value.
 * Showing it as a percentage would present a made-up number as a finding, so it
 * is cleared on load and the job reads as unverified until it is scanned again.
 *
 * **The field rename.** `redFlags` became `anomalies`. Without this, every
 * stored scan would render as a clean posting: the findings are still in
 * storage under the old key, and nothing would read them. The score is left
 * alone — a stored score was measured and stays measured, whatever the
 * findings are called now.
 */
export function migrateScannedJobs(stored: unknown): ScannedJob[] {
  if (!Array.isArray(stored)) return [];

  return (stored as ScannedJob[]).map((job) => {
    const scanResult = job?.scanResult;
    if (!scanResult || typeof scanResult !== 'object') return job;

    // `redFlags` is not on the type any more, so it is reached through `unknown`.
    // Checked for shape rather than cast straight to Anomaly[]: a stored entry
    // could hold anything, and a malformed list must not become a render crash.
    const { redFlags: legacyFlags, ...rest } = scanResult as unknown as Record<
      string,
      unknown
    >;
    // Destructured rather than spread-and-overwrite: a key set to `undefined`
    // still exists on the object, so `toHaveProperty` would report it and a
    // stored entry would carry a dead field forever.
    const renamed: ScanResult = Array.isArray(legacyFlags)
      ? { ...(rest as unknown as ScanResult), anomalies: legacyFlags as Anomaly[] }
      : (rest as unknown as ScanResult);

    if (renamed.riskScored === true) return { ...job, scanResult: renamed };

    return {
      ...job,
      scanResult: {
        ...renamed,
        riskScored: false,
        riskScore: null,
        riskLevel: null,
        riskLabel: 'Not Scored',
      },
    };
  });
}
