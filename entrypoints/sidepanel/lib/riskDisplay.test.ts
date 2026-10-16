import { describe, it, expect } from 'vitest';
import {
  describeScoreBasis,
  shouldElevateEvidence,
  type VerificationRun,
} from './riskDisplay';
import type { ScanResult, ScanRiskLevel } from '../types';

function result(over: Partial<ScanResult> = {}): ScanResult {
  return {
    riskLevel: 'low',
    riskLabel: 'Low Risk',
    riskScored: true,
    riskScore: 5,
    riskDescription: '',
    scanningTarget: 'Scanned Element',
    anomalies: [],
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

describe('describeScoreBasis', () => {
  /**
   * The line that says what the number rests on has to branch on whether the
   * lookup *ran*, not on whether it changed the number.
   *
   * It used to read `scoreBreakdown.sources`, which names the stages that
   * contributed a value. The refutation stage returns `null` rather than 0 when
   * nothing was refuted — deliberately, so "learned nothing" stays distinct from
   * "measured zero" — which means `sources` reads `['posting']` after a lookup
   * that ran and confirmed every claim. Keyed off it, the panel told the reader
   * their employer had never been checked, after it had been.
   *
   * The common good outcome is the one that was being misreported, so each state
   * is pinned separately and the two that were previously conflated are pinned
   * as *different strings*.
   */
  const basis = (verificationRun: VerificationRun) =>
    describeScoreBasis({ verificationRun });

  it('says the employer was not checked when it never ran', () => {
    expect(basis('never')).toMatch(/was not checked/i);
  });

  it('does not claim the employer was unchecked after a lookup that confirmed everything', () => {
    // The regression. A panel that told a reader to discount an unchecked verdict
    // would have them discount a corroborated one.
    expect(basis('confirmed')).not.toMatch(/not checked/i);
    expect(basis('confirmed')).toMatch(/no source contradicted/i);
  });

  it('names the source of the contradiction when a claim was refuted', () => {
    // It used to match /web evidence/, which passed only because the sentence
    // opened "Posting findings and web evidence: 80/100." With the number gone
    // there is nothing named, so the sentence now says what actually happened:
    // a retrieved source contradicted a claim.
    expect(basis('refuted')).toMatch(/retrieved source contradicted/i);
    expect(basis('refuted')).not.toMatch(/web evidence/i);
  });

  it('prints no number in any state', () => {
    // The removal this change exists for. Every state used to open
    // "Posting findings...: 80/100." A number there implied a precision no stage
    // could defend and invited "how did you get 80?" with no answer available.
    for (const state of ['never', 'failed', 'confirmed', 'refuted'] as const) {
      const line = basis(state);
      expect(line, state).not.toMatch(/\d+\s*\/\s*100/);
      expect(line, state).not.toMatch(/\d+/);
      expect(line, state).not.toMatch(/Posting findings/);
    }
  });

  it('says the lookup did not complete, rather than that nothing was checked', () => {
    // Three different facts, three different sentences. A lookup that failed is
    // not a lookup that never ran, and telling the reader it never ran would
    // send them looking for a check that did happen.
    expect(basis('failed')).toMatch(/did not complete/i);
    expect(basis('failed')).not.toMatch(/was not checked/i);
  });

  it('no longer takes a score at all', () => {
    // It used to assert `47/100` appeared in every state, which is the exact
    // behaviour being removed. There is no runtime assertion that replaces it:
    // passing an extra property to a destructured parameter is silently ignored
    // in JavaScript rather than throwing, so "does it reject a score" would pass
    // vacuously, and `Object.keys` on a function is always empty. The two real
    // guards are `tsc`, which rejects a caller passing `riskScore`, and the test
    // above, which pins that no state prints a digit. A third copy here would add
    // nothing, so this asserts only what is genuinely checkable: the call takes
    // the one argument it advertises and produces a figure-free sentence.
    const line = describeScoreBasis({ verificationRun: 'confirmed' });
    expect(line).not.toMatch(/\d/);
    expect(line).toMatch(/no source contradicted/i);
  });

  it('keeps the four states distinguishable from one another', () => {
    // Negative assertions alone would pass for a function returning the same
    // string everywhere. What matters is that a reader can tell which of the
    // four situations they are in.
    const states = (['never', 'failed', 'confirmed', 'refuted'] as VerificationRun[]).map((s) =>
      basis(s)
    );

    expect(new Set(states).size).toBe(4);
  });

  it('does not attribute the score to the posting alone when evidence contributed', () => {
    expect(basis('refuted')).not.toMatch(/postings? findings only/i);
    expect(basis('confirmed')).not.toMatch(/postings? findings only/i);
  });
});
