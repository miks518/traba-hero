import { describe, it, expect } from 'vitest';
import { groupBy, statusPresentation } from './checkPresentation';
import type { VerificationItem } from '../../types';

function item(status: VerificationItem['status']): VerificationItem {
  return { label: 'Channel Match', status, explanation: 'x' };
}

/**
 * One vocabulary, four states.
 *
 * The panel used to carry two incompatible status systems, and this is the seam
 * that makes them one. The assertions below are the properties the rest of the
 * panel relies on: every state lands in a group, the four states are
 * distinguishable from each other, and a state the vocabulary does not know is
 * not silently dropped from a column that already showed the check.
 */
describe('grouping the four states', () => {
  it('puts every state in a group and loses none', () => {
    const items = [
      item('confirmed'),
      item('supported'),
      item('unknown'),
      item('contradicted'),
    ];

    const grouped = groupBy(items).filter((g) => g.items.length > 0);

    expect(grouped).toHaveLength(4);
    expect(grouped.map((g) => g.key).sort()).toEqual([
      'confirmed',
      'contradicted',
      'supported',
      'unknown',
    ]);
  });

  it('keeps confirmed and supported apart, so a record that was never compared is not called confirmed', () => {
    const grouped = groupBy([item('confirmed'), item('supported')]);

    const confirmed = grouped.find((g) => g.key === 'confirmed');
    const supported = grouped.find((g) => g.key === 'supported');
    expect(confirmed?.items).toHaveLength(1);
    expect(supported?.items).toHaveLength(1);
    expect(confirmed?.label).not.toBe(supported?.label);
  });

  it('folds a state the vocabulary does not know into could-not-verify', () => {
    // A stored reading written before this vocabulary, or a provider answering
    // outside it. Silence would hide a card the reader was already shown.
    const unknownState = { label: 'Channel Match', status: 'green' } as unknown as VerificationItem;

    const grouped = groupBy([unknownState]).filter((g) => g.items.length > 0);

    expect(grouped).toHaveLength(1);
    expect(grouped[0].key).toBe('unknown');
  });

  it('orders the groups contradicted first, then the confirmations, then silence', () => {
    const grouped = groupBy([
      item('unknown'),
      item('supported'),
      item('confirmed'),
      item('contradicted'),
    ]);

    expect(grouped.map((g) => g.key)).toEqual([
      'contradicted',
      'confirmed',
      'supported',
      'unknown',
    ]);
  });
});

describe('marking one check from its own state', () => {
  it('gives contradicted the critical treatment', () => {
    const mark = statusPresentation('contradicted');
    expect(mark.icon).toBe('gpp_bad');
    expect(mark.cls).toBe('text-chip-critical-text');
  });

  it('gives the two confirmations different marks, so the weaker one is visible', () => {
    expect(statusPresentation('confirmed').icon).not.toBe(statusPresentation('supported').icon);
  });

  it('gives unknown the question mark, not an alarm glyph', () => {
    // `gpp_maybe` is a shield with an exclamation point — a claim about the
    // employer. The claim here is only that the check settled nothing.
    expect(statusPresentation('unknown').icon).toBe('question_mark');
  });
});
