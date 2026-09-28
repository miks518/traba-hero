import { describe, it, expect } from 'vitest';
import { shouldElevateEvidence } from './riskDisplay';
import type { ScanResult, ScanRiskLevel } from '../types';

function result(over: Partial<ScanResult> = {}): ScanResult {
  return {
    riskLevel: 'low',
    riskLabel: 'Low Risk',
    riskScored: true,
    riskScore: 5,
    riskDescription: '',
    scanningTarget: 'Scanned Element',
    redFlags: [],
    flagsCritical: false,
    isJobPosting: true,
    ...over,
  };
}

function at(level: ScanRiskLevel | null, settled = true): ScanResult {
  return result({
    riskLevel: level,
    verificationLoading: !settled,
  });
}

describe('shouldElevateEvidence', () => {
  it('promotes the evidence for a high score', () => {
    expect(shouldElevateEvidence(at('high'))).toBe(true);
  });

  it('promotes the evidence for a critical score', () => {
    expect(shouldElevateEvidence(at('critical'))).toBe(true);
  });

  it('leaves moderate where it is', () => {
    expect(shouldElevateEvidence(at('moderate'))).toBe(false);
  });

  it('leaves low where it is', () => {
    expect(shouldElevateEvidence(at('low'))).toBe(false);
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
    expect(shouldElevateEvidence(at('high', false))).toBe(false);
  });

  it('waits while the offer analysis is still running', () => {
    expect(
      shouldElevateEvidence(result({ riskLevel: 'high', offerAnalysisLoading: true }))
    ).toBe(false);
  });

  it('promotes once a failed verification has settled', () => {
    // A failed lookup still leaves a real posting-stage score. The evidence is
    // known, so leading with it is correct even though the employer was not.
    expect(
      shouldElevateEvidence(
        result({ riskLevel: 'critical', verificationLoading: false, verificationError: true })
      )
    ).toBe(true);
  });

  it('promotes a high score that has no employer at all', () => {
    // Nothing to verify, so nothing is pending. The posting score is final.
    expect(
      shouldElevateEvidence(
        result({ riskLevel: 'high', verificationLoading: false, companyName: null })
      )
    ).toBe(true);
  });
});
