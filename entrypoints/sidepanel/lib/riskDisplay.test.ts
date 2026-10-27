import { describe, it, expect } from 'vitest';
import { shouldElevateEvidence } from './riskDisplay';
import type { ScanResult, Assessment } from '../types';

function result(over: Partial<ScanResult> = {}): ScanResult {
  return {
    assessment: 'green',
    assessmentLabel: 'Nothing found against it',
    assessed: true,
    assessmentBreakdown: undefined,
    scanningTarget: 'Scanned Element',
    anomalies: [],
    isJobPosting: true,
    riskDescription: '',
    ...over,
  };
}

function at(assessment: Assessment | null, settled = true): ScanResult {
  return result({
    assessment,
    verificationLoading: !settled,
  });
}

describe('shouldElevateEvidence', () => {
  it('promotes the evidence for a red assessment', () => {
    expect(shouldElevateEvidence(at('red'))).toBe(true);
  });

  it('promotes the evidence for the scam-shape yellow', () => {
    // A prohibited request at an employer the record never established is the
    // reading a jobseeker most needs to see before they reply. The rule
    // arrives from the assessment breakdown, not the colour.
    expect(
      shouldElevateEvidence({
        ...at('yellow'),
        elevationRule: 'prohibited_at_unestablished_employer',
      })
    ).toBe(true);
  });

  it('leaves the unclassified yellow where it is', () => {
    // Uncertainty about the request class is what the chip word already says;
    // the evidence does not lead for it.
    expect(
      shouldElevateEvidence({
        ...at('yellow'),
        elevationRule: 'unclassified_request',
      })
    ).toBe(false);
  });

  it('leaves a confirmed-employer fee demand where it is', () => {
    expect(
      shouldElevateEvidence({
        ...at('yellow'),
        elevationRule: 'prohibited_at_confirmed_employer',
      })
    ).toBe(false);
  });

  it('leaves green where it is', () => {
    expect(shouldElevateEvidence(at('green'))).toBe(false);
  });

  it('does not promote an unverified result', () => {
    // "Unverified" is a missing measurement, not a high one. Promoting it
    // would lead with evidence for a score we never produced.
    expect(shouldElevateEvidence(at(null))).toBe(false);
  });

  it('waits while verification is still running', () => {
    // The assessment at this point is the posting stage's alone. It can still
    // move once the employer check blends in, and rearranging under the reader
    // mid-flight is worse than a moment's wait.
    expect(shouldElevateEvidence(at('red', false))).toBe(false);
  });

  it('waits while the offer analysis is still running', () => {
    expect(
      shouldElevateEvidence(result({ assessment: 'red', offerAnalysisLoading: true }))
    ).toBe(false);
  });

  it('promotes once a failed verification has settled', () => {
    // A failed lookup still leaves a real posting-stage assessment. The
    // evidence is known, so leading with it is correct even though the
    // employer was not.
    expect(
      shouldElevateEvidence(
        result({ assessment: 'red', verificationLoading: false, verificationError: true })
      )
    ).toBe(true);
  });

  it('promotes a red assessment that has no employer at all', () => {
    // Nothing to verify, so nothing is pending. The posting assessment is final.
    expect(
      shouldElevateEvidence(
        result({ assessment: 'red', verificationLoading: false, companyName: null })
      )
    ).toBe(true);
  });
});
