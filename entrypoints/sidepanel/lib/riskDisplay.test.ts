import { describe, expect, it } from 'vitest';
import { isUnverifiedEmployer } from './riskDisplay';

/**
 * A posting that names no employer with no red flags in it is not "low risk" —
 * it is unchecked. "Low Risk, 0" would tell a reader the post was cleared,
 * which is not something we measured. The distinction is only for that exact
 * combination: a red flag is real evidence about the post and is scored as
 * usual, and a named employer can be verified normally.
 */
describe('isUnverifiedEmployer', () => {
  it('is true when the posting names no employer and has no red flags', () => {
    expect(isUnverifiedEmployer({ isJobPosting: true, companyName: null, redFlagCount: 0 })).toBe(true);
  });

  it('is false when a red flag is present, so the severity score stands', () => {
    expect(isUnverifiedEmployer({ isJobPosting: true, companyName: null, redFlagCount: 1 })).toBe(false);
  });

  it('is false when the posting is not a job offer at all', () => {
    expect(isUnverifiedEmployer({ isJobPosting: false, companyName: null, redFlagCount: 0 })).toBe(false);
  });

  it('is false when the employer is named, because it can be verified', () => {
    expect(isUnverifiedEmployer({ isJobPosting: true, companyName: 'Jollibee', redFlagCount: 0 })).toBe(false);
  });

  it('treats a whitespace-only name as no name', () => {
    expect(isUnverifiedEmployer({ isJobPosting: true, companyName: '   ', redFlagCount: 0 })).toBe(true);
  });
});
