import { describe, it, expect } from 'vitest';
import { assessmentFor, actionsFor, NO_ASSESSMENT, VERIFYING } from './assessmentCopy';

/**
 * The assessment -> headline contract.
 *
 * **This is the reader-visible half of the assessment grid, and it is pinned.**
 * The backend decides the assessment (green | yellow | red), this file decides
 * the words, and the reader sees the words. A change to either half that breaks
 * the other is caught here.
 *
 * None of the three headlines may name a cause the grid does not guarantee.
 * "Contradicted" is the red headline. "Caution" is the one advisory word,
 * backed by the grid rule in the breakdown. "Nothing found against it" claims
 * resemblance to the ordinary case, never that the posting is safe.
 */
describe('what each assessment tells the reader', () => {
  it('says exactly "Contradicted" for red, and nothing else', () => {
    // It has to be true for every path to red, not just the channel one.
    expect(assessmentFor('red').headline).toBe('Contradicted');
  });

  it('gives yellow the advisory word', () => {
    // Yellow is uncertainty, from either grid rule: an unclassifiable request,
    // or a prohibited one whose asker the record never established.
    expect(assessmentFor('yellow').headline).toBe('Caution');
    expect(assessmentFor('yellow').headline).not.toContain('Contradicted');
  });

  it('never claims the posting is safe for green', () => {
    // Green means an ordinary ask and a record that did not contradict it - not
    // a clean bill of health. The headline reports resemblance, not clearance.
    expect(assessmentFor('green').headline).toBe('Nothing found against it');
    expect(assessmentFor('green').headline).not.toContain('Proceed');
    expect(assessmentFor('green').headline).not.toContain('safe');
    expect(assessmentFor('green').headline).not.toContain('Contradicted');
  });

  it('never names a contradiction below red', () => {
    // Red is the only card that says something is wrong.
    for (const assessment of ['green', 'yellow'] as const) {
      const headline = assessmentFor(assessment).headline;
      expect(headline).not.toMatch(/contradicted/i);
      expect(headline).not.toMatch(/not right/i);
    }
  });
});

describe('the actions the reader is offered', () => {
  it('red offers the reader the choice to not send money or documents', () => {
    const actions = actionsFor('red');
    expect(actions.lead).toMatch(/do not send/i);
    expect(actions.rest).toMatch(/money|document/i);
    // The red actions never soften into "proceed"
    const allText = [actions.lead, actions.rest, actions.secondLead, actions.secondRest].join(' ').toLowerCase();
    expect(allText).not.toContain('proceed');
  });

  it('green does not carry an alarm, and does not claim clearance', () => {
    const actions = actionsFor('green');
    const allText = [actions.lead, actions.rest, actions.secondLead, actions.secondRest].join(' ').toLowerCase();
    // Green offers the reader's next steps, not warnings — and never the
    // retired "Proceed", which claimed a clearance the grid never measured.
    expect(allText).not.toMatch(/stop/i);
    expect(allText).not.toMatch(/do not send/i);
    expect(allText).not.toMatch(/warning/i);
    expect(allText).not.toMatch(/caution/i);
    expect(allText).not.toContain('proceed');
  });

  it('yellow tells the reader what to settle first', () => {
    const actions = actionsFor('yellow');
    const allText = [actions.lead, actions.rest, actions.secondLead, actions.secondRest].join(' ').toLowerCase();
    // Yellow should tell the reader what specific thing to check
    expect(allText).toMatch(/what|who|confirm/i);
  });
});

describe('the states with no assessment behind them', () => {
  it('declines to assert a assessment when there is none', () => {
    // A posting that named no employer, or a verification that could not
    // complete. "No assessment on this one" is the honest answer.
    expect(assessmentFor(null).headline).toBe('No assessment on this one');
    expect(assessmentFor(undefined).headline).toBe('No assessment on this one');
    expect(NO_ASSESSMENT.headline).not.toContain('Contradicted');
  });

  it('asserts nothing while the employer lookup is running', () => {
    // The intermediate state is not the assessment. The copy says only what is
    // true, which is that a check is in flight.
    expect(VERIFYING.headline).toBe('Checking this job post');
    expect(VERIFYING.headline).not.toContain('Contradicted');
  });
});
