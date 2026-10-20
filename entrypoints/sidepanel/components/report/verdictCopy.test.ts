import { describe, it, expect } from 'vitest';
import { verdictFor, NO_VERDICT, VERIFYING } from './verdictCopy';

/**
 * The level -> headline contract.
 *
 * **This is the reader-visible half of the Channel Match fix, and it was
 * unpinned.** The backend fixtures in `backend/tests/test_channel_match_regressions.py`
 * assert the *level* a posting lands on - `low` for the free-email Knollridges
 * post, `critical` for the Fake CHED one. Nothing asserted what those levels
 * render, so the mapping below could have been edited to say "Do not proceed"
 * for `low` and every test in the repo would still have passed, with the exact
 * bug this table exists to prevent back in the panel.
 *
 * The two halves are a contract: the backend decides the level, this file
 * decides the words, and the reader sees the words. A change to either half
 * that breaks the other is caught here.
 */
describe('what each level tells the reader to do', () => {
  it('says exactly "Do not proceed" for a critical posting, and nothing else', () => {
    // The one headline that is a flat stop. It is reserved for `critical`,
    // which needs a combined score above 75 - a single weak finding cannot
    // reach it.
    expect(verdictFor('critical').headline).toBe('Do not proceed');
  });

  it('gives a high posting a conditional stop, not the flat one', () => {
    // "Do not proceed without checking first" is a different instruction from
    // "Do not proceed", and the difference is the whole point of the strong
    // channel floor landing on 51 rather than 76. Pinned exactly, so a later
    // edit that collapses the two cannot pass unnoticed.
    expect(verdictFor('high').headline).toBe('Do not proceed without checking first');
  });

  it('never tells a low or moderate posting to stop', () => {
    // The free-email case lands on `low` and the single-fee case on
    // `moderate`. Neither may carry a stop instruction in any form - not the
    // exact headline, not a prefix of it, not a variant. A level that reads
    // "Do not proceed" here would put the reader off a posting over one
    // unconfirmed email address.
    for (const level of ['low', 'moderate'] as const) {
      const headline = verdictFor(level).headline;
      expect(headline).not.toContain('Do not proceed');
      expect(headline).not.toContain('do not proceed');
      expect(headline).not.toContain('Stop');
      expect(headline).not.toContain('stop');
    }
  });

  it('keeps the Knollridges case a proceed', () => {
    // The backend fixture
    // `test_knollridges_does_not_become_do_not_proceed` produces the level
    // `low` for a real employer whose posting used a Gmail address while its
    // own site was `knollridges.com.ph`. This is the other half of that
    // assertion: the level the backend chose, rendered.
    const headline = verdictFor('low').headline;

    expect(headline).toBe('Proceed, with a quick check');
    expect(headline).not.toBe('Do not proceed');
  });

  it('keeps the Fake CHED case a stop', () => {
    // The backend fixture
    // `test_fake_ched_stays_critical_and_the_chred_domain_is_red` produces the
    // level `critical` for a poster using the CHED seal and `ched.gov.ph`
    // while sending applicants to `chred-region6.org` and demanding fees.
    // This is the other half of that assertion.
    expect(verdictFor('critical').headline).toBe('Do not proceed');
  });
});

describe('the two states with no level behind them', () => {
  it('declines to assert a level when there is none', () => {
    // A posting that named no employer, or a verification that could not
    // complete. "No verdict on this one" is the honest answer; borrowing the
    // `low` headline would claim the posting was cleared.
    expect(verdictFor(null).headline).toBe('No verdict on this one');
    expect(verdictFor(undefined).headline).toBe('No verdict on this one');
    expect(NO_VERDICT.headline).not.toContain('Do not proceed');
  });

  it('asserts nothing while the employer lookup is running', () => {
    // The intermediate level is not the verdict. The copy says only what is
    // true, which is that a check is in flight.
    expect(VERIFYING.headline).toBe('Checking this company');
    expect(VERIFYING.headline).not.toContain('Do not proceed');
  });
});
