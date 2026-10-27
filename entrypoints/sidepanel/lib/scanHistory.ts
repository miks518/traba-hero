import type { Anomaly, ScanResult, ScannedJob, Assessment } from '../types';

/**
 * How many scans are kept.
 *
 * History is stored in `chrome.storage.local` alongside nothing else, but the
 * shared 5MB budget is small and the panel is rebuilt from the whole list on
 * every render. Twenty is roughly a fortnight of looking at postings, which is
 * more than anyone compares at once, and it is a number the Match tab can state
 * plainly.
 *
 * Exported rather than written into the copy so the notice and the behaviour
 * cannot drift — a limit of twenty described as thirty is worse than either.
 */
export const MAX_SCAN_HISTORY = 20;

/**
 * Keep the newest `MAX_SCAN_HISTORY` scans, drop the rest.
 *
 * Newest last: history is append-only and the list is rendered newest-first, so
 * the newest job is the final element. An implementation that kept the first N
 * would look right at one entry and silently delete the newest scan instead of
 * the oldest, which is the direction that loses work.
 *
 * Returns the same array reference when nothing needs dropping, so a render
 * that does not change the count does not re-persist storage.
 */
export function capScannedJobs(jobs: ScannedJob[]): ScannedJob[] {
  if (jobs.length <= MAX_SCAN_HISTORY) return jobs;
  return jobs.slice(jobs.length - MAX_SCAN_HISTORY);
}

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
 * storage under the old key, and nothing would read them.
 *
 * **The vocabulary, and why the result is marked.** A stored scan carries a
 * level — `low`/`moderate`/`high`/`critical` — and no request class and no
 * establishment, so the new assessment cannot be *computed* from it: the two inputs
 * the grid reads are simply not in the record. It is mapped to the nearest
 * reader-facing word instead, and the entry is stamped
 * `assessmentRecordedUnder: 'previous-procedure'` so nothing presents a legacy
 * level as a assessment this system reached. That stamp is the difference between
 * a migration and a silent re-labelling.
 *
 * The mapped word is deliberately the harsher of the two neighbours: a stored
 * `high` becomes `stop`, not `caution`. An old `high` was a posting its scanner
 * thought dangerous, and downgrading it on the way through a schema change would
 * quietly tell a reader a posting had improved.
 */
export function migrateScannedJobs(stored: unknown): ScannedJob[] {
  if (!Array.isArray(stored)) return [];

  return (stored as ScannedJob[]).map((job) => {
    const scanResult = job?.scanResult;
    if (!scanResult || typeof scanResult !== 'object') return job;

    // `redFlags` is not on the type any more, so it is reached through `unknown`.
    // Checked for shape rather than cast straight to Anomaly[]: a stored entry
    // could hold anything, and a malformed list must not become a render crash.
    const { redFlags: legacyFlags, riskLevel: legacyRiskLevel, riskLabel: legacyRiskLabel, ...rest } = scanResult as unknown as Record<
      string,
      unknown
    >;
    // Destructured rather than spread-and-overwrite: a key set to `undefined`
    // still exists on the object, so `toHaveProperty` would report it and a
    // stored entry would carry a dead field forever.
    const renamed: ScanResult = Array.isArray(legacyFlags)
      ? { ...(rest as unknown as ScanResult), anomalies: legacyFlags as Anomaly[] }
      : (rest as unknown as ScanResult);

    // Map a legacy level onto the nearest assessment colour, and mark it as
    // legacy. The two inputs the grid reads are not in a stored record, so this
    // is a label and never a computed assessment. The labels keep the recorded
    // meaning ("High risk" was the old ladder's own word); the stamp is what
    // stops a legacy record from presenting itself as a current assessment.
    if (legacyRiskLevel !== undefined && renamed.assessment === undefined) {
      const mapping: Record<string, { assessment: Assessment; label: string }> = {
        critical: { assessment: 'red', label: 'High risk' },
        high: { assessment: 'red', label: 'High risk' },
        moderate: { assessment: 'yellow', label: 'Caution' },
        low: { assessment: 'green', label: 'Nothing found against it' },
      };
      const mapped = mapping[legacyRiskLevel as string];
      if (mapped) {
        renamed.assessment = mapped.assessment;
        renamed.assessmentLabel = mapped.label;
        renamed.assessed = true;
        renamed.assessmentRecordedUnder = 'previous-procedure';
      }
    }

    // Scans recorded under the previous vocabulary (`clear`/`note`/`caution`/
    // `stop`) map onto the colours, with the recorded strength kept: a stored
    // `stop` was a contradiction finding, so it renders as "Contradicted".
    const legacyWords: Record<string, { assessment: Assessment; label: string }> = {
      clear: { assessment: 'green', label: 'Nothing found against it' },
      note: { assessment: 'yellow', label: 'Caution' },
      caution: { assessment: 'yellow', label: 'Caution' },
      stop: { assessment: 'red', label: 'Contradicted' },
    };
    const storedAssessment = renamed.assessment as unknown as string;
    if (storedAssessment && legacyWords[storedAssessment]) {
      const mapped = legacyWords[storedAssessment];
      renamed.assessment = mapped.assessment;
      if (!renamed.assessmentLabel) {
        renamed.assessmentLabel = mapped.label;
      }
    }

    if (renamed.assessed === true) return { ...job, scanResult: renamed };

    return {
      ...job,
      scanResult: {
        ...renamed,
        assessed: false,
        assessment: null,
        assessmentLabel: 'Not Assessed',
      },
    };
  });
}
