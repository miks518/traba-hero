import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import React from 'react';
import { ActionBlock } from './ActionBlock';
import type { Assessment } from '../../types';

/**
 * The action block used to speak only from its authored table, keyed to the
 * assessment family alone. A `caution` posting got the same two sentences whether
 * the fee was ₱150 to a GCash account or an unexplained "training kit" —
 * generic advice that does not refer to the thing being assessed, which the
 * design record already named as a failure shape for the chips row.
 *
 * Verify writes a recommendation for the checked posting, and the backend
 * screens it before it reaches the wire (`clean_recommendation`: an accusation,
 * hedge or absolute becomes absent). So the block renders that text when it
 * exists and falls back to the authored copy in the states verification did
 * not reach — no run yet, an error, a rejected recommendation.
 *
 * The bullet colour stays code-owned in both branches: text may be the model's,
 * colour may not.
 */

afterEach(cleanup);

function block(props: {
  assessment?: Assessment | null;
  recommendation?: string;
}): string {
  const { container } = render(
    React.createElement(ActionBlock, {
      assessment: props.assessment ?? null,
      recommendation: props.recommendation,
    }),
  );
  return container.querySelector('[data-role="action-block"]')?.textContent ?? '';
}

describe('the action block prefers the verify recommendation', () => {
  it('renders the recommendation when verification produced one', () => {
    const text = block({
      assessment: 'yellow',
      recommendation: 'The results show no company named QuickCash Solutions. Ask the poster to confirm the fee recipient in writing.',
    });

    expect(text).toContain('Ask the poster to confirm the fee recipient in writing.');
    expect(text).not.toContain('Ask who receives the fee and why.');
  });

  it('renders one row, not the authored pair, when the recommendation stands', () => {
    const text = block({
      assessment: 'red',
      recommendation: 'A retrieved source accounts for this request.',
    });

    // The authored second line must be absent alongside a recommendation.
    expect(text).not.toContain('Check the company yourself');
  });

  it('falls back to the authored copy when no recommendation arrived', () => {
    const text = block({ assessment: 'red' });

    expect(text).toContain('Do not send money or documents.');
    expect(text).toContain('Check the company yourself');
  });

  it('falls back when the recommendation is blank', () => {
    // The backend sends an empty string for a screened-out recommendation; the
    // authored table is the safe and still-actionable degradation.
    const text = block({ assessment: 'yellow', recommendation: '   ' });

    expect(text).toContain('Ask what the offer asks for and why.');
  });

  it('renders the code-authored fallback recommendation on the no-assessment path', () => {
    // A recommendation with a null assessment is a real state on the wire: the
    // no-employer path and the search-failed path both send a code-authored
    // fallback recommendation with `assessment: null`. That text is authored, not
    // model-written, so it outranks the generic table and the grey bullet is
    // the honest tone for it.
    const text = block({ assessment: null, recommendation: 'Confirm the employer independently before submitting personal details.' });

    expect(text).toContain('Confirm the employer independently before submitting personal details.');
    expect(text).not.toContain('No assessment on this one.');
  });
});
