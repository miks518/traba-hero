import { describe, it, expect } from 'vitest';
import { shouldElevateEvidence } from './riskDisplay';
import type { ScanResult, Verdict } from '../types';

function result(over: Partial<ScanResult> = {}): ScanResult {
  return {
    verdict: 'clear',
    verdictLabel: 'Proceed',
    verdicted: true,
    verdictBreakdown: undefined,
    scanningTarget: 'Scanned Element',
    anomalies: [],
    flagsCritical: false,
    isJobPosting: true,
    riskDescription: '',
    ...over,
  };
}

function at(verdict: Verdict | null, settled = true): ScanResult {
  return result({
    verdict,
    verificationLoading: !settled,
  });
}

describe('shouldElevateEvidence', () => {
  it('promotes the evidence for a stop verdict', () => {
    expect(shouldElevateEvidence(at('stop'))).toBe(true);
  });

  it('promotes the evidence for a caution verdict', () => {
    expect(shouldElevateEvidence(at('caution'))).toBe(true);
  });

  it('leaves note where it is', () => {
    expect(shouldElevateEvidence(at('note'))).toBe(false);
  });

  it('leaves clear where it is', () => {
    expect(shouldElevateEvidence(at('clear'))).toBe(false);
  });

  it('does not promote an unverified result', () => {
    // "Unverified" is a missing measurement, not a high one. Promoting it
    // would lead with evidence for a score we never produced.
    expect(shouldElevateEvidence(at(null))).toBe(false);
  });

  it('waits while verification is still running', () => {
    // The level at this point is the posting stage's alone. It can still move
    // once the employer score blends in, and rearranging under the reader
    // mid-flight is worse than a moment's wait.
    expect(shouldElevateEvidence(at('stop', false))).toBe(false);
  });

  it('waits while the offer analysis is still running', () => {
    expect(
      shouldElevateEvidence(result({ verdict: 'stop', offerAnalysisLoading: true }))
    ).toBe(false);
  });

  it('promotes once a failed verification has settled', () => {
    // A failed lookup still leaves a real posting-stage score. The evidence is
    // known, so leading with it is correct even though the employer was not.
    expect(
      shouldElevateEvidence(
        result({ verdict: 'stop', verificationLoading: false, verificationError: true })
      )
    ).toBe(true);
  });

  it('promotes a stop verdict that has no employer at all', () => {
    // Nothing to verify, so nothing is pending. The posting score is final.
    expect(
      shouldElevateEvidence(
        result({ verdict: 'stop', verificationLoading: false, companyName: null })
      )
    ).toBe(true);
  });
});
