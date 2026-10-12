/**
 * The provenance line under the gauge is a control, and these pin the three
 * things that decide what it is.
 *
 * `happy-dom` performs no flex layout and zeroes every `getBoundingClientRect()`,
 * so nothing here asserts position or that the scroll looked smooth. What is
 * asserted is the mechanism that produces it: which element renders, the class
 * that carries the press, and that the handler runs.
 */

import React from 'react';
import { fireEvent, render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RiskGauge } from './RiskGauge';

const BASE = {
  score: 40,
  riskLevel: 'low' as const,
  riskLabel: 'Low Risk',
};

describe('the provenance line', () => {
  it('is a button when there is something below to go to', () => {
    const { container } = render(
      React.createElement(RiskGauge, { ...BASE, anomalyCount: 1, onShowEvidence: () => {} })
    );

    const button = container.querySelector('[data-role="provenance-jump"]');
    expect(button).toBeTruthy();
    expect(button!.tagName).toBe('BUTTON');
    expect(button!.textContent).toBe('1 thing in this post differs from normal.');
  });

  it('carries the tactile treatment and its press', () => {
    // DESIGN.md: a hard-shadowed button with no press is a container. The
    // class is what carries the affordance, so the class is the assertion.
    const { container } = render(
      React.createElement(RiskGauge, { ...BASE, anomalyCount: 3, onShowEvidence: () => {} })
    );

    const button = container.querySelector('[data-role="provenance-jump"]')!;
    expect(button.className).toContain('tactile-btn-accent');
    // The inverse variant, not the green CTA accent: this is navigation, not
    // the primary action on the screen.
    expect(button.className).toContain('tactile-btn-inverse');
    expect(button.className).not.toContain('tactile-btn-error');
  });

  it('does not submit a form it happens to sit inside', () => {
    const { container } = render(
      React.createElement(RiskGauge, { ...BASE, anomalyCount: 2, onShowEvidence: () => {} })
    );

    expect(container.querySelector('[data-role="provenance-jump"]')!.getAttribute('type')).toBe(
      'button'
    );
  });

  it('runs the handler when pressed', () => {
    let pressed = 0;
    const { container } = render(
      React.createElement(RiskGauge, {
        ...BASE,
        anomalyCount: 1,
        onShowEvidence: () => { pressed += 1; },
      })
    );

    fireEvent.click(container.querySelector('[data-role="provenance-jump"]')!);
    expect(pressed).toBe(1);
  });

  it('stays plain text when there is nothing to scroll to', () => {
    // "Nothing in this post stands out" describes an empty list. A control
    // that scrolls nowhere is worse than the sentence it replaced.
    const { container } = render(
      React.createElement(RiskGauge, { ...BASE, anomalyCount: 0, onShowEvidence: () => {} })
    );

    expect(container.querySelector('[data-role="provenance-jump"]')).toBeNull();
    expect(container.textContent).toContain('Nothing in this post stands out');
  });

  it('stays plain text with no handler, rather than rendering a dead control', () => {
    const { container } = render(React.createElement(RiskGauge, { ...BASE, anomalyCount: 5 }));

    expect(container.querySelector('[data-role="provenance-jump"]')).toBeNull();
    expect(container.textContent).toContain('5 things in this post differ from normal');
  });

  it('renders nothing at all when the count is unknown', () => {
    const { container } = render(
      React.createElement(RiskGauge, { ...BASE, onShowEvidence: () => {} })
    );

    expect(container.querySelector('[data-role="provenance-jump"]')).toBeNull();
  });
});