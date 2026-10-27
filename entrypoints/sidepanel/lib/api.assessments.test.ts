import { describe, it, expect } from 'vitest';
import { mapAnomalyAssessments } from './api';

/**
 * The verify wire's assessment list, mapped once at the boundary.
 *
 * Two distinctions are load-bearing and both are easy to erase here: an absent
 * key is not an empty list, and a status the client does not know is not a
 * status it may pass through to a lookup table that has no entry for it.
 */
describe('mapping the assessment list from the verify wire', () => {
  it('keeps the index, the sentence, and the source of a stale assessment', () => {
    const mapped = mapAnomalyAssessments([
      {
        index: 2,
        status: 'stale',
        finding: 'The careers page lists the exam fee.',
        source_title: 'Careers',
        source_url: 'https://employer.example/careers',
      },
    ]);

    expect(mapped).toEqual([
      {
        index: 2,
        status: 'stale',
        finding: 'The careers page lists the exam fee.',
        sourceTitle: 'Careers',
        sourceUrl: 'https://employer.example/careers',
      },
    ]);
  });

  it('maps an unrecognised status to unknown rather than passing it through', () => {
    // A card that received `green` would look up no strip and render the finding
    // as if it had been checked and passed. `unknown` is the honest default, and
    // it is the same word the backend uses for "nothing was settled".
    const mapped = mapAnomalyAssessments([
      { index: 1, status: 'green', finding: 'something' },
      { index: 2, status: 'RED', finding: 'something else' },
    ]);

    expect(mapped?.[0].status).toBe('unknown');
    expect(mapped?.[1].status).toBe('unknown');
  });

  it('preserves absent as undefined and an empty list as an empty list', () => {
    // The panel says different things for "this reading predates the check" and
    // "the check ran and produced no assessment". Defaulting one to the other makes
    // one of those notes false.
    expect(mapAnomalyAssessments(undefined)).toBeUndefined();
    expect(mapAnomalyAssessments([])).toEqual([]);
  });

  it('drops an entry that is not an object', () => {
    const mapped = mapAnomalyAssessments([
      null as never,
      { index: 1, status: 'unknown', finding: 'kept' },
    ]);

    expect(mapped).toHaveLength(1);
    expect(mapped?.[0].finding).toBe('kept');
  });

  it('does not invent an index the wire did not carry', () => {
    const mapped = mapAnomalyAssessments([
      { status: 'unknown', finding: 'no index' },
    ]);

    expect(mapped?.[0].index).toBeUndefined();
  });
});
