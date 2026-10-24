/**
 * Reputation renders only when there is something to say.
 *
 * The rule under test is `shouldShowCheck`, which hides exactly one case: an
 * `unknown` Reputation. Both exclusions around it are asserted below, and they
 * are the reason this is a predicate with a test per branch rather than a
 * `filter` tucked into the component.
 *
 * The hidden case exists because of the sentence it removed. An unsettled
 * Reputation could only report that the results contained no reviews, and it was
 * phrased as a sentence — "The search results do not contain any scam reports,
 * fraud warnings, formal complaints, or employee reviews for <company>" — which
 * puts "scam" and "fraud" beside a named company in reader-facing text in order
 * to report nothing. That is the failure the prompt rules exist to prevent, so
 * the verify prompt now asks for an empty finding there and this hides the card
 * that would have carried it.
 */
import { describe, it, expect } from 'vitest';

import { shouldShowCheck } from './riskDisplay';

/** The one hidden case. */
const HIDDEN = { label: 'Reputation', status: 'unknown' } as const;

describe('shouldShowCheck', () => {
  it('hides an unsettled Reputation', () => {
    expect(shouldShowCheck(HIDDEN)).toBe(false);
  });

  it('shows a Reputation that a result contradicted', () => {
    // The overcorrection that matters most. A contradicted Reputation is a
    // retrieved source disagreeing with the posting, so a rule keyed on the
    // label rather than on label-plus-state would hide the single most
    // consequential card in the panel.
    expect(shouldShowCheck({ label: 'Reputation', status: 'contradicted' })).toBe(true);
  });

  it('shows a Reputation that a result confirmed', () => {
    expect(shouldShowCheck({ label: 'Reputation', status: 'confirmed' })).toBe(true);
  });

  it('shows an unsettled check that is not Reputation', () => {
    // The second overcorrection. These cards summarise what the search actually
    // returned, sources included, so an all-unknown result still reads as a
    // summary. Hiding every unknown would empty the panel and lose the sources.
    for (const label of [
      'Company Existence',
      'Official Registration',
      'Location / Branch',
      'Channel Match',
      'Similar Offers',
    ]) {
      expect(shouldShowCheck({ label, status: 'unknown' }), label).toBe(true);
    }
  });

  it('shows every state for a check that is not Reputation', () => {
    for (const status of ['confirmed', 'supported', 'unknown', 'contradicted'] as const) {
      expect(shouldShowCheck({ label: 'Company Existence', status }), status).toBe(true);
    }
  });

  it('matches the label without regard to case or padding', () => {
    // The labeled-text fallback parser takes whatever label the model wrote, so
    // an exact-case match would let the model dodge the rule by capitalising.
    for (const label of ['reputation', 'REPUTATION', '  Reputation  ']) {
      expect(shouldShowCheck({ label, status: 'unknown' }), label).toBe(false);
    }
  });

  it('does not hide a check whose label merely contains the word', () => {
    // Substring matching would swallow any future category named after
    // reputation, which is the kind of quiet widening a `includes` invites.
    for (const label of ['Reputation Signals', 'Public Reputation Index']) {
      expect(shouldShowCheck({ label, status: 'unknown' }), label).toBe(true);
    }
  });
});

describe('the panel derives emptiness from what it renders', () => {
  it('reports nothing to show when the only check was the hidden one', () => {
    // `EvidenceSummary` computes `hasItems` from the filtered list, not from
    // `result.items`. If it computed it from the raw list, hiding the only card
    // would leave the heading "Evidence Summary" above an empty column, which
    // asserts evidence was summarised when none was.
    const items = [HIDDEN];
    expect(items.filter(shouldShowCheck).length).toBe(0);
  });

  it('still reports items when one of several is hidden', () => {
    const items = [
      { label: 'Company Existence', status: 'unknown' as const },
      HIDDEN,
      { label: 'Reputation', status: 'contradicted' as const },
    ];
    expect(items.filter(shouldShowCheck).map((i) => i.label)).toEqual([
      'Company Existence',
      'Reputation',
    ]);
  });
});
