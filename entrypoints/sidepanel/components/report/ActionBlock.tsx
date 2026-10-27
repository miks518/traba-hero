import React from 'react';
import { Icon } from '../common';
import { actionsFor, shareChipsFor, NO_ASSESSMENT_BULLET } from './assessmentCopy';
import type { Assessment } from '../../types';

export interface ActionBlockProps {
  assessment: Assessment | null;
  codes?: string[];
  /**
   * The verify stage's recommendation, written for this posting.
   *
   * **Verify owns the text; code owns the colour.** The backend screens the
   * model's words before they reach the wire (`clean_recommendation`: an
   * accusation, hedge or absolute becomes absent, never shown), so a non-empty
   * string here is guarded prose about *this* posting — what the results showed
   * and one step the reader can take. The authored table is the fallback for
   * the states verification did not reach: no run yet, an error, a rejected
   * recommendation. The bullet follows the assessment's tone in both branches —
   * colour is code-owned, never model-written.
   */
  recommendation?: string;
  /**
   * The offer pass's "what to check" line, written for this posting.
   *
   * The offer pass runs when there is no employer to look up, so it has no
   * retrieved evidence to draw on — only the posting's own words. Its
   * `what_to_check` is the concrete step the reader can take, and it is the
   * text the action block should show in place of the authored table, which
   * is keyed to the assessment family alone and cannot refer to this posting.
   */
  whatToCheck?: string;
}

export function ActionBlock(props: ActionBlockProps) {
  const { assessment, codes, recommendation, whatToCheck } = props;
  const actions = actionsFor(assessment);
  const chips = shareChipsFor(codes);

  const bullet = assessment ? actions.bullet : NO_ASSESSMENT_BULLET;

  // Verify owns the text when it ran; the offer pass owns it when there was no
  // employer to look up. Either way the authored table is the fallback for the
  // states neither reached: no run yet, an error, a screened-out recommendation.
  const verified = (recommendation || whatToCheck || '').trim();
  const row = (leadText: string | null, bodyText: string) =>
    React.createElement(
      'div',
      { className: 'flex items-start gap-3' },
      React.createElement('span', { 'aria-hidden': true, className: 'mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ' + bullet }),
      React.createElement(
        'p',
        { className: 'text-body-sm leading-relaxed text-on-surface min-w-0' },
        leadText && React.createElement('strong', { className: 'font-bold' }, leadText),
        leadText ? ' ' : null,
        bodyText
      )
    );

  const section = React.createElement(
    'section',
    { className: 'flex flex-col gap-2', 'data-role': 'action-block' },
    React.createElement(
      'h3',
      { className: 'text-headline-sm font-headline font-bold px-1' },
      'What to do now'
    ),
    React.createElement(
      'div',
      { className: 'tactile-card bg-surface-container-lowest border border-outline-variant/20 p-4 flex flex-col gap-3' },
      verified ? row(null, verified) : row(actions.lead, actions.rest),
      !verified && row(actions.secondLead, actions.secondRest),
      chips && chips.length > 0 && React.createElement(
        'div',
        { className: 'flex flex-wrap gap-2 mt-1' },
        chips.map((chip, i) => React.createElement(
          'span',
          { key: i, className: 'inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-outline-variant/30 text-label-sm text-on-surface-variant' },
          React.createElement(Icon, { name: 'do_not_disturb_on', className: 'text-xs shrink-0' }),
          chip
        ))
      )
    )
  );

  return section;
}
