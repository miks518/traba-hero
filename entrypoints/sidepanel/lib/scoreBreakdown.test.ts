import { describe, expect, it } from 'vitest';
import { toScoreBreakdown } from './scoreBreakdown';

/**
 * The wire key and what it holds drifted apart.
 *
 * `verification_score` used to be the employer stage's share of a blend, and is
 * now a 0–50 refutation sum: only a retrieved source that contradicts a claim
 * the posting made contributes, so a clean employer record contributes zero.
 * The wire key stayed (a deployed backend and stored scans depend on it) and the
 * client's field was renamed. This is the boundary, and nothing else in the
 * panel reads the wire's spelling — so it has to be asserted here, or a
 * regression is invisible everywhere.
 */

const wire = {
  source: 'risk_calculator',
  high_count: 1,
  mid_count: 0,
  low_count: 2,
  weights: { high: 40, mid: 12, low: 4 },
  posting_score: 48,
  verification_score: 25,
  final_score: 73,
  sources: ['posting', 'verification'],
};

describe('toScoreBreakdown', () => {
  it('names the employer stage for what it now measures', () => {
    expect(toScoreBreakdown(wire)?.refutationScore).toBe(25);
  });

  it('leaves no wire key on the result', () => {
    // The failure this guards is the convenient one: spreading the wire object
    // and adding a new field. That leaves `verification_score` readable on a
    // ScanResult, and reading it is the mistake the rename exists to prevent.
    expect(Object.keys(toScoreBreakdown(wire) ?? {})).not.toContain('verification_score');
  });

  it('keeps a stage that did not contribute distinct from one that scored zero', () => {
    // `null` is "the employer stage never ran"; `0` is "it ran and nothing was
    // refuted". Collapsing them would let an unlookable employer read as a
    // checked one.
    expect(toScoreBreakdown({ posting_score: 40, verification_score: null })?.refutationScore).toBeNull();
    expect(toScoreBreakdown({ posting_score: 40, verification_score: 0 })?.refutationScore).toBe(0);
  });

  it('omits the stage entirely when the wire omitted it', () => {
    // An older backend, or a scan taken before the employer stage existed.
    // Inventing a zero here would claim a stage ran when none did.
    expect('refutationScore' in (toScoreBreakdown({ posting_score: 40 }) ?? {})).toBe(false);
  });

  it('keeps the sources list the panel reads', () => {
    // The provenance line under the gauge is built from this, and it is the
    // only breakdown field anything renders.
    expect(toScoreBreakdown(wire)?.sources).toEqual(['posting', 'verification']);
  });

  it('carries the posting stage and the final score across', () => {
    const result = toScoreBreakdown(wire);
    expect(result?.postingScore).toBe(48);
    expect(result?.finalScore).toBe(73);
    expect(result?.weights).toEqual({ high: 40, mid: 12, low: 4 });
  });

  it('reports no breakdown when there was none', () => {
    // `score_breakdown: null` is what a scan with nothing to measure sends.
    // Returning `{}` would make "nothing was measured" indistinguishable from
    // "nothing contributed".
    expect(toScoreBreakdown(null)).toBeUndefined();
    expect(toScoreBreakdown(undefined)).toBeUndefined();
  });
});
