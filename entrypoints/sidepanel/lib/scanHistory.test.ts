import { describe, it, expect } from 'vitest';
import { updateScannedJob } from './scanHistory';
import type { ScannedJob, ScanResult } from '../types';

function result(over: Partial<ScanResult> = {}): ScanResult {
  return {
    riskLevel: 'low',
    riskLabel: 'Low Risk',
    riskScored: true,
    riskScore: 0,
    scanningTarget: 'Scanned Element',
    redFlags: [],
    flagsCritical: false,
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
  it('replaces the score once verification finishes', () => {
    // The bug: the history entry is written at scan time with the posting-stage
    // score, then verification blends in an employer score and the panel moves
    // to 12 while history stays at 0.
    const stored = [job('a', { riskScore: 0, riskLevel: 'low' })];

    const next = updateScannedJob(stored, 'a', result({ riskScore: 12, riskLevel: 'low' }));

    expect(next[0].scanResult.riskScore).toBe(12);
  });

  it('does not append a second entry for the same job', () => {
    const stored = [job('a')];
    const next = updateScannedJob(stored, 'a', result({ riskScore: 12 }));
    expect(next).toHaveLength(1);
  });

  it('leaves other jobs untouched', () => {
    const stored = [job('a'), job('b', { riskScore: 40 })];
    const next = updateScannedJob(stored, 'a', result({ riskScore: 12 }));
    expect(next[1].scanResult.riskScore).toBe(40);
  });

  it('is a no-op when the id is unknown', () => {
    const stored = [job('a')];
    const next = updateScannedJob(stored, 'missing', result({ riskScore: 12 }));
    expect(next).toEqual(stored);
  });

  it('carries the verification result and score breakdown through', () => {
    // The employer stage also produces evidence the reader can open. Updating
    // only the number would leave history claiming a score it cannot explain.
    const stored = [job('a')];
    const verified = result({
      riskScore: 12,
      verificationResult: {
        items: [{ label: 'Official Registration', status: 'green', explanation: 'CS201500123' }],
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

    const next = updateScannedJob(stored, 'a', result({ riskScore: 0, verificationLoading: false, verificationError: true }));

    expect(next[0].scanResult.verificationLoading).toBe(false);
    expect(next[0].scanResult.verificationError).toBe(true);
  });
});
