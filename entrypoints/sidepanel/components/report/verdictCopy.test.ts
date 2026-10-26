import { describe, it, expect } from 'vitest';
import { verdictFor, actionsFor, NO_VERDICT, VERIFYING } from './verdictCopy';

/**
 * The verdict -> headline contract.
 *
 * **This is the reader-visible half of the verdict grid, and it is pinned.**
 * The backend decides the verdict (clear | note | caution | stop), this file
 * decides the words, and the reader sees the words. A change to either half
 * that breaks the other is caught here.
 *
 * "Do not proceed" is the ace card: it is said only for `stop`, and `stop`
 * requires a contradiction (the government branch or a lookalike domain).
 * Every other verdict states what was found and what the record showed.
 */
describe('what each verdict tells the reader to do', () => {
  it('says exactly "Do not proceed" for stop, and nothing else', () => {
    // The one headline that is a flat stop. It is reserved for `stop`,
    // which requires a contradiction - the government branch or a lookalike.
    expect(verdictFor('stop').headline).toBe('Do not proceed');
  });

  it('gives caution a conditional instruction, not the flat stop', () => {
    // Caution means the request is prohibited but the employer is unknown.
    // The reader should settle the fee recipient/reason first.
    expect(verdictFor('caution').headline).not.toContain('Do not proceed');
    expect(verdictFor('caution').headline).not.toContain('stop');
    expect(verdictFor('caution').headline).toContain('Caution');
  });

  it('gives note a confirm instruction, not a stop', () => {
    // Note means the request is prohibited/unclassified but the employer is confirmed/supported.
    // The reader should check the employer's own site.
    expect(verdictFor('note').headline).not.toContain('Do not proceed');
    expect(verdictFor('note').headline).not.toContain('stop');
    expect(verdictFor('note').headline).toContain('Note');
  });

  it('gives clear a proceed instruction', () => {
    // Clear means the request is ordinary and the employer is not contradicted.
    // The reader should proceed.
    expect(verdictFor('clear').headline).toBe('Proceed');
    expect(verdictFor('clear').headline).not.toContain('Do not proceed');
    expect(verdictFor('clear').headline).not.toContain('stop');
  });

  it('never tells the reader to stop below stop', () => {
    // "Do not proceed" is the ace card. Only `stop` may carry it.
    for (const verdict of ['clear', 'note', 'caution'] as const) {
      const headline = verdictFor(verdict).headline;
      expect(headline).not.toMatch(/do not proceed/i);
      expect(headline).not.toMatch(/stop/i);
    }
  });
});

describe('the actions the reader is offered', () => {
  it('stop offers the reader the choice to not send money or documents', () => {
    const actions = actionsFor('stop');
    expect(actions.lead).toMatch(/do not send/i);
    expect(actions.rest).toMatch(/money|document/i);
    // No "proceed" in the stop instructions
    const allText = [actions.lead, actions.rest, actions.secondLead, actions.secondRest].join(' ').toLowerCase();
    expect(allText).not.toContain('proceed');
  });

  it('clear does not carry an alarm', () => {
    const actions = actionsFor('clear');
    const allText = [actions.lead, actions.rest, actions.secondLead, actions.secondRest].join(' ').toLowerCase();
    // Clear should offer the reader's next steps, not warnings
    expect(allText).not.toMatch(/stop/i);
    expect(allText).not.toMatch(/do not send/i);
    expect(allText).not.toMatch(/warning/i);
    expect(allText).not.toMatch(/caution/i);
  });

  it('caution tells the reader what to settle first', () => {
    const actions = actionsFor('caution');
    const allText = [actions.lead, actions.rest, actions.secondLead, actions.secondRest].join(' ').toLowerCase();
    // Caution should tell the reader what specific thing to check
    expect(allText).toMatch(/what|who|confirm/i);
  });
});

describe('the states with no verdict behind them', () => {
  it('declines to assert a verdict when there is none', () => {
    // A posting that named no employer, or a verification that could not
    // complete. "No verdict on this one" is the honest answer.
    expect(verdictFor(null).headline).toBe('No verdict on this one');
    expect(verdictFor(undefined).headline).toBe('No verdict on this one');
    expect(NO_VERDICT.headline).not.toContain('Do not proceed');
  });

  it('asserts nothing while the employer lookup is running', () => {
    // The intermediate state is not the verdict. The copy says only what is
    // true, which is that a check is in flight.
    expect(VERIFYING.headline).toBe('Checking this company');
    expect(VERIFYING.headline).not.toContain('Do not proceed');
  });
});