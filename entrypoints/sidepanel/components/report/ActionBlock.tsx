import React from 'react';
import { Icon } from '../common';
import { actionsFor, shareChipsFor, NO_VERDICT_BULLET } from './verdictCopy';
import type { Verdict } from '../../types';

export interface ActionBlockProps {
  verdict: Verdict | null;
  codes?: string[];
}

export function ActionBlock(props: ActionBlockProps) {
  const { verdict, codes } = props;
  const actions = actionsFor(verdict);
  const chips = shareChipsFor(codes);

  const bullet = verdict ? actions.bullet : NO_VERDICT_BULLET;

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
      React.createElement(
        'div',
        { className: 'flex items-start gap-3' },
        React.createElement('span', { 'aria-hidden': true, className: 'mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ' + bullet }),
        React.createElement(
          'p',
          { className: 'text-body-sm leading-relaxed text-on-surface min-w-0' },
          React.createElement('strong', { className: 'font-bold' }, actions.lead),
          ' ',
          actions.rest
        )
      ),
      React.createElement(
        'div',
        { className: 'flex items-start gap-3' },
        React.createElement('span', { 'aria-hidden': true, className: 'mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ' + bullet }),
        React.createElement(
          'p',
          { className: 'text-body-sm leading-relaxed text-on-surface min-w-0' },
          React.createElement('strong', { className: 'font-bold' }, actions.secondLead),
          ' ',
          actions.secondRest
        )
      ),
      chips && chips.length > 0 && React.createElement(
        'div',
        { className: 'flex flex-wrap gap-2 mt-1' },
        chips.map((chip, i) => React.createElement(
          'span',
          { key: i, className: 'inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-outline-variant/30 text-label-sm text-on-surface-variant' },
          React.createElement('Icon', { name: 'do_not_disturb_on', className: 'text-xs shrink-0' }),
          chip
        ))
      )
    )
  );

  return section;
}