import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { RiskGauge } from './RiskGauge';

afterEach(() => cleanup());

/**
 * A posting with no employer name and no red flags has a posting-stage score of
 * 0, which renders as "0 / Low Risk". That reads as "we checked and it's fine",
 * which is not what happened — the employer was never checked at all.
 */
describe('RiskGauge unverified state', () => {
  it('does not claim Low Risk when the employer was never checked', () => {
    render(<RiskGauge score={0} riskLabel="Low Risk" riskLevel="low" unverified />);

    expect(screen.queryByText('Low Risk')).toBeNull();
    expect(screen.queryByText('0')).toBeNull();
    expect(screen.getByText('Unverified')).not.toBeNull();
  });

  it('explains what was and was not checked', () => {
    render(<RiskGauge score={0} riskLabel="Low Risk" riskLevel="low" unverified />);

    const note = screen.getByText(/could not be checked/i);
    expect(note).not.toBeNull();
  });

  it('still shows Low Risk when a red flag put the score above zero', () => {
    render(<RiskGauge score={40} riskLabel="High Risk" riskLevel="high" />);

    expect(screen.getByText('High Risk')).not.toBeNull();
    expect(screen.getByText('40')).not.toBeNull();
  });

  it('shows Low Risk normally when not unverified', () => {
    render(<RiskGauge score={0} riskLabel="Low Risk" riskLevel="low" />);

    expect(screen.getByText('Low Risk')).not.toBeNull();
  });

  it('paints the unverified state grey, not amber', () => {
    // Amber is the 'moderate' level. Nothing was measured here, so borrowing
    // amber would read as a mid risk score rather than an unchecked one.
    const { container } = render(<RiskGauge score={0} riskLevel="low" unverified />);

    const html = container.innerHTML;
    expect(html).not.toContain('hsl(45, 78%, 44%)');
    expect(html).toContain('text-outline');
  });
});

/**
 * The gauge is the first thing a reader looks at, so it should read as live.
 * The unverified ring is grey rather than amber: nothing was measured, and
 * amber is already spoken for by the 'moderate' level.
 */
describe('RiskGauge ring animation', () => {
  it('shows a grey ring in the unverified state, not an empty one', () => {
    const { container } = render(<RiskGauge score={0} riskLevel="low" unverified />);

    const progress = container.querySelectorAll('circle')[1];
    expect(progress).toBeTruthy();
    // A fully-offset ring is invisible, which is what lost the ring before.
    expect(progress?.getAttribute('stroke-dashoffset')).not.toBe(
      progress?.getAttribute('stroke-dasharray'),
    );
  });

  it('pulses the unverified ring in grey', () => {
    const { container } = render(<RiskGauge score={0} riskLevel="low" unverified />);

    expect(container.innerHTML).toContain('ring-pulse');
    expect(container.innerHTML).toMatch(/var\(--color-outline\)|outline/);
  });

  it('glows and pulses the scored ring in its risk colour', () => {
    const { container } = render(<RiskGauge score={75} riskLevel="high" riskLabel="High Risk" />);

    const html = container.innerHTML;
    expect(html).toContain('ring-pulse');
    // The glow takes its colour from the level, so it tracks the score.
    expect(html).toContain('--ring-glow-color');
  });

  it('clips the glow inside the card so the border cannot cut through it', () => {
    // A drop-shadow bleeds past the element it is on. Left unclipped it escapes
    // the rounded card and the border draws a hard line across the glow.
    const { container } = render(<RiskGauge score={75} riskLevel="high" riskLabel="High Risk" />);
    expect(container.querySelector('section')?.className).toContain('overflow-hidden');

    cleanup();
    const unverified = render(<RiskGauge score={0} riskLevel="low" unverified />);
    expect(unverified.container.querySelector('section')?.className).toContain('overflow-hidden');
  });
});
