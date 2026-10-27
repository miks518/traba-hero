import { describe, it, expect } from 'vitest';
import {
  MAX_VERIFY_ANOMALIES,
  mergeAnomalyAssessments,
  selectVerifiableIndices,
} from './useScanSession';
import type { Anomaly } from '../types';

function anomaly(id: string, code?: string): Anomaly {
  return {
    id,
    title: `Finding ${id}`,
    description: `Description ${id}`,
    icon: 'warning',
    ...(code !== undefined ? { code } : {}),
  };
}

describe('choosing which findings one verify request carries', () => {
  it('caps at the backend limit and keeps the findings that demand something from the reader', () => {
    // A formatting note or an ordinary applicant packet must not take the
    // place of a fee demand when the request can only carry twenty. The rank
    // is the finding's taxonomy code, not a model judgement — see
    // `docs/decisions/scan-severity-removal.md`.
    const anomalies = Array.from({ length: 25 }, (_, index) =>
      anomaly(
        String(index),
        index === 24 ? 'FEE_MANDATORY' : index === 23 ? 'DOCUMENTS_VIA_THIRD_PARTY' : undefined,
      ),
    );

    const selected = selectVerifiableIndices(anomalies);

    expect(selected).toHaveLength(MAX_VERIFY_ANOMALIES);
    expect(selected).toContain(24);
    expect(selected).toContain(23);
    expect(selected).not.toContain(19);
    // Ascending original order, so the numbered findings block reads in the same
    // order as the cards.
    expect(selected).toEqual([...selected].sort((a, b) => a - b));
  });

  it('keeps every finding when there are fewer than the cap', () => {
    const selected = selectVerifiableIndices([anomaly('a'), anomaly('b', 'FEE_MANDATORY')]);
    expect(selected).toEqual([0, 1]);
  });

  it('keeps a money demand and an identity exposure over ordinary packets', () => {
    // The order the cap protects: what the posting asks the reader to give
    // up. A fee demand and a documents-via-third-party finding survive the cap;
    // the ordinary applicant packet and the uncoded notes do not.
    const anomalies = [
      anomaly('packet', 'APPLICATION_DOCUMENTS'),
      anomaly('documents', 'DOCUMENTS_VIA_THIRD_PARTY'),
      ...Array.from({ length: 22 }, (_, i) => anomaly(`note-${i}`)),
      anomaly('fee', 'FEE_MANDATORY'),
    ];
    const selected = selectVerifiableIndices(anomalies);

    expect(selected).toHaveLength(MAX_VERIFY_ANOMALIES);
    expect(selected).toContain(1);
    expect(selected).toContain(24);
    // The uncoded notes rank below both; only the early ones fit, so a late
    // note is what the cap drops.
    expect(selected).not.toContain(23);
  });
});

describe('attaching assessments back to the findings', () => {
  it('maps a request index through the selected list to the original finding', () => {
    // The request carried findings 0 and 2; the model's index 1 means the first
    // of those, which is original finding 0.
    const anomalies = [anomaly('a'), anomaly('b'), anomaly('c')];
    const merged = mergeAnomalyAssessments(
      anomalies,
      [0, 2],
      [
        { index: 1, status: 'stale', finding: 'first', sourceUrl: 'https://x' },
        { index: 2, status: 'contradicted', finding: 'second', sourceUrl: 'https://y' },
      ],
      true,
    );

    expect(merged[0].assessment?.finding).toBe('first');
    expect(merged[2].assessment?.finding).toBe('second');
    // The finding the request did not carry says so, rather than losing its card.
    expect(merged[1].assessment?.status).toBe('unknown');
    expect(merged[1].assessment?.finding).toContain('more findings');
  });

  it('does not invent a reason for an omitted finding when the check never ran', () => {
    const merged = mergeAnomalyAssessments(
      [anomaly('a'), anomaly('b'), anomaly('c')],
      [0, 2],
      [],
      false,
    );

    expect(merged[1].assessment).toBeUndefined();
  });

  it('keeps the first assessment when an index is duplicated', () => {
    const merged = mergeAnomalyAssessments(
      [anomaly('a')],
      [0],
      [
        { index: 1, status: 'stale', finding: 'first' },
        { index: 1, status: 'contradicted', finding: 'second' },
      ],
      true,
    );

    expect(merged[0].assessment?.finding).toBe('first');
  });

  it('ignores an index outside the selected list', () => {
    const merged = mergeAnomalyAssessments(
      [anomaly('a'), anomaly('b')],
      [0, 1],
      [{ index: 3, status: 'stale', finding: 'nowhere' }],
      false,
    );

    expect(merged.every((item) => item.assessment === undefined)).toBe(true);
  });

  it('leaves a selected finding without a assessment absent, for the card to explain', () => {
    const merged = mergeAnomalyAssessments(
      [anomaly('a'), anomaly('b')],
      [0, 1],
      [{ index: 2, status: 'unknown', finding: 'only the second' }],
      true,
    );

    expect(merged[0].assessment).toBeUndefined();
    expect(merged[1].assessment?.finding).toBe('only the second');
  });

  it('clears a previous assessment when the new check ran and did not return one', () => {
    // Re-verification: the old `stale` must not survive as if this run had
    // produced it. The card's amber "no assessment recorded" is the honest state.
    const previous = {
      ...anomaly('a'),
      assessment: {
        status: 'stale' as const,
        finding: 'the previous reading',
        sourceUrl: 'https://old.example/careers',
      },
    };
    const merged = mergeAnomalyAssessments([previous], [0], [], true);

    expect(merged[0].assessment).toBeUndefined();
  });

  it('keeps a stored assessment when the check did not run', () => {
    // A saved scan from the feature's own era keeps its assessment; only a new
    // run that came back empty may clear it.
    const stored = {
      ...anomaly('a'),
      assessment: {
        status: 'stale' as const,
        finding: 'the stored reading',
        sourceUrl: 'https://employer.example/careers',
      },
    };
    const merged = mergeAnomalyAssessments([stored], [0], [], false);

    expect(merged[0].assessment?.finding).toBe('the stored reading');
  });

  it('attaches to the original finding even when the selected list is out of order', () => {
    const merged = mergeAnomalyAssessments(
      [anomaly('a'), anomaly('b'), anomaly('c')],
      [2, 0],
      [{ index: 1, status: 'stale', finding: 'for c', sourceUrl: 'https://x' }],
      false,
    );

    expect(merged[2].assessment?.finding).toBe('for c');
    expect(merged[0].assessment).toBeUndefined();
  });
});
