import React from 'react';
import { Icon } from '../common';
import { actionsFor, shareChipsFor, NO_VERDICT_BULLET } from './verdictCopy';
import type { Verdict } from '../../types';

export interface ActionBlockProps {
  verdict: Verdict | null;
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
   * recommendation. The bullet follows the verdict's tone in both branches —
   * colour is code-owned, never model-written.
   */
  recommendation?: string;
}

export function ActionBlock(props: ActionBlockProps) {
  const { verdict, codes, recommendation } = props;
  const actions = actionsFor(verdict);
  const chips = shareChipsFor(codes);

  const bullet = verdict ? actions.bullet : NO_VERDICT_BULLET;

  // The verify recommendation replaces both authored lines when it exists —
  // one row, the checked posting's own words. Without one the authored table
  // renders exactly as before.
  const verified = (recommendation || '').trim();
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
