import { describe, it, expect } from 'vitest';
import { migrateScannedJobs, updateScannedJob, capScannedJobs, MAX_SCAN_HISTORY } from './scanHistory';
import type { ScannedJob, ScanResult } from '../types';

/**
 * `capScannedJobs` — the newest N, oldest dropped.
 *
 * History is append-only in memory and the newest is rendered first, so the
 * newest job is the *last* element. An implementation that kept the first N
 * would look correct at the default of one entry and quietly delete the newest
 * scan instead of the oldest, which is the direction that loses work.
 */
describe('scan history length', () => {
  const job = (id: string): ScannedJob =>
    ({ id, title: id, summary: '', timestamp: '', scanResult: {} }) as unknown as ScannedJob;

  it('keeps the twenty most recent scans', () => {
    const many = Array.from({ length: 25 }, (_, i) => job(`job-${i}`));

    const kept = capScannedJobs(many);

    expect(kept).toHaveLength(MAX_SCAN_HISTORY);
    // job-24 is the newest, job-5 the oldest survivor, job-4 the first dropped.
    expect(kept[kept.length - 1].id).toBe('job-24');
    expect(kept[0].id).toBe('job-5');
  });

  it('keeps everything while there is room', () => {
    const few = Array.from({ length: 3 }, (_, i) => job(`job-${i}`));

    expect(capScannedJobs(few)).toEqual(few);
  });

  it('keeps exactly the cap when the count lands on it', () => {
    const exact = Array.from({ length: MAX_SCAN_HISTORY }, (_, i) => job(`job-${i}`));

    expect(capScannedJobs(exact)).toHaveLength(MAX_SCAN_HISTORY);
  });

  it('drops the oldest when one more arrives at the cap', () => {
    const full = Array.from({ length: MAX_SCAN_HISTORY }, (_, i) => job(`job-${i}`));

    const kept = capScannedJobs([...full, job('job-newest')]);

    expect(kept).toHaveLength(MAX_SCAN_HISTORY);
    expect(kept.some((j: ScannedJob) => j.id === 'job-0')).toBe(false);
    expect(kept[kept.length - 1].id).toBe('job-newest');
  });
});

function result(over: Partial<ScanResult> = {}): ScanResult {
  return {
    assessment: 'clear',
    assessmentLabel: 'Proceed',
    assessed: true,
    assessmentBreakdown: undefined,
    scanningTarget: 'Scanned Element',
    anomalies: [],
    isJobPosting: true,
    riskDescription: '',
    ...over,
  };
}

function job(id: string, over: Partial<ScanResult> = {}): ScannedJob {
  return {
    id,
    title: `Job ${id}`,
    summary: 'summary',
    timestamp: '2026-01-01T00:00:00.000Z',
    scanResult: result(over),
  };
}

describe('updateScannedJob', () => {
  it('replaces the assessment once verification finishes', () => {
    // The bug: the history entry is written at scan time with the posting-stage
    // assessment, then verification blends in an employer score and the panel moves
    // to 'note' while history stays at null.
    const stored = [job('a', { assessment: null })];

    const next = updateScannedJob(stored, 'a', result({ assessment: 'note' }));

    expect(next[0].scanResult.assessment).toBe('note');
  });

  it('does not append a second entry for the same job', () => {
    const stored = [job('a')];
    const next = updateScannedJob(stored, 'a', result({ assessment: 'note' }));
    expect(next).toHaveLength(1);
  });

  it('leaves other jobs untouched', () => {
    const stored = [job('a'), job('b', { assessment: 'caution' })];
    const next = updateScannedJob(stored, 'a', result({ assessment: 'note' }));
    expect(next[1].scanResult.assessment).toBe('caution');
  });

  it('is a no-op when the id is unknown', () => {
    const stored = [job('a')];
    const next = updateScannedJob(stored, 'missing', result({ assessment: 'note' }));
    expect(next).toEqual(stored);
  });

  it('carries the verification result and assessment breakdown through', () => {
    // The employer stage also produces evidence the reader can open. Updating
    // only the number would leave history claiming a score it cannot explain.
    const stored = [job('a')];
    const verified = result({
      assessment: 'note',
      verificationResult: {
        items: [{ label: 'Official Registration', status: 'confirmed', explanation: 'CS201500123' }],
        report: 'r',
        recommendation: 'x',
      },
    });

    const next = updateScannedJob(stored, 'a', verified);

    expect(next[0].scanResult.verificationResult?.items[0].explanation).toBe('CS201500123');
  });

  it('records a failed verification rather than leaving it looking in flight', () => {
    // verificationLoading is set at scan time when a company name exists, so an
    // entry left there forever would show a spinner that never resolves.
    const stored = [job('a', { verificationLoading: true })];

    const next = updateScannedJob(stored, 'a', result({ assessment: 'note', verificationLoading: false, verificationError: true }));

    expect(next[0].scanResult.verificationLoading).toBe(false);
    expect(next[0].scanResult.verificationError).toBe(true);
  });
});

describe('migrateScannedJobs renames the findings field', () => {
  /** A stored entry written before `redFlags` became `anomalies`. */
  const legacy = (over: Record<string, unknown> = {}): unknown => [
    {
      id: 'a',
      title: 'Job a',
      summary: 'summary',
      timestamp: '2026-01-01T00:00:00.000Z',
      scanResult: {
        riskLevel: 'moderate',
        riskLabel: 'Moderate Risk',
        riskScored: true,
        riskScore: 52,
        scanningTarget: 'Scanned Element',
        flagsCritical: true,
        isJobPosting: true,
        riskDescription: '',
        redFlags: [
          { id: 'flag-0', title: 'Asks applicants to pay a processing fee', description: 'r', icon: 'warning', severity: 'high' },
        ],
        ...over,
      },
    },
  ];

  it('moves the stored findings onto the new key', () => {
    // Without this the findings stay in storage under `redFlags` and nothing
    // reads them, so every scan taken before the rename renders as a clean
    // posting — the worst possible failure for this product.
    const next = migrateScannedJobs(legacy());

    expect(next[0].scanResult.anomalies).toHaveLength(1);
    expect(next[0].scanResult.anomalies[0].title).toBe(
      'Asks applicants to pay a processing fee',
    );
  });

  it('maps a stored level onto the nearest assessment word', () => {
    // `moderate` becomes `caution`: the old level was a score band, the new word
    // is a warning, and the two nearest are those.
    const next = migrateScannedJobs(legacy());

    expect(next[0].scanResult.assessment).toBe('caution');
    expect(next[0].scanResult.assessmentLabel).toBe('Caution');
  });

  it('marks the mapping as a legacy reading, not a assessment this system reached', () => {
    // The whole difference between a migration and a silent re-labelling. A
    // stored record has no request class and no establishment, so the grid
    // cannot run on it; the word is a label and the flag says so.
    const next = migrateScannedJobs(legacy());

    expect(next[0].scanResult.assessmentRecordedUnder).toBe('previous-procedure');
    // And neither grid input is invented to fill the gap.
    expect(next[0].scanResult.requestClass).toBeUndefined();
  });

  it('maps a stored high to stop rather than softening it', () => {
    // An old `high` was a posting its scanner thought dangerous. Downgrading it
    // on the way through a schema change would quietly tell a reader a posting
    // had improved.
    const next = migrateScannedJobs(legacy({ riskLevel: 'high', riskLabel: 'High Risk' }));

    expect(next[0].scanResult.assessment).toBe('stop');
    expect(next[0].scanResult.assessmentRecordedUnder).toBe('previous-procedure');
  });

  it('leaves a record that already carries a assessment untouched', () => {
    const next = migrateScannedJobs(
      legacy({ assessment: 'clear', assessmentLabel: 'Proceed', assessed: true, requestClass: 'ordinary' }),
    );

    expect(next[0].scanResult.assessment).toBe('clear');
    expect(next[0].scanResult.assessmentRecordedUnder).toBeUndefined();
  });

  it('drops the old key rather than keeping both', () => {
    const next = migrateScannedJobs(legacy());

    expect(next[0].scanResult).not.toHaveProperty('redFlags');
  });

  it('ignores a legacy value that is not a list', () => {
    // Storage can hold anything. A malformed value must not become findings.
    const next = migrateScannedJobs(legacy({ redFlags: 'not-a-list' }));

    expect(next[0].scanResult.anomalies).toBeUndefined();
  });

  it('still clears a synthesised assessment it finds on the way past', () => {
    // The original purpose of this function is unchanged by the rename.
    const next = migrateScannedJobs(legacy({ assessed: false, assessment: 'stop' }));

    expect(next[0].scanResult.assessment).toBeNull();
    expect(next[0].scanResult.assessmentLabel).toBe('Not Assessed');
  });
});
