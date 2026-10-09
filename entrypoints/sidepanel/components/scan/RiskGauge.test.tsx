import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { RiskGauge } from './RiskGauge';

afterEach(() => cleanup());

/**
 * A posting with no employer name and no anomalies has a posting-stage score of
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

  it('still shows Low Risk when an anomaly put the score above zero', () => {
    render(<RiskGauge score={40} riskLabel="High Risk" riskLevel="high" anomalyCount={1} />);

    expect(screen.getByText('High Risk')).not.toBeNull();
    expect(screen.getByText('40')).not.toBeNull();
  });

  it('shows Low Risk normally when not unverified', () => {
    render(<RiskGauge score={0} riskLabel="Low Risk" riskLevel="low" anomalyCount={0} />);

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
 * A bare number with no stated unit or basis is unreadable.
 *
 * A tester read "12" as meaningless and asked what it was out of. Two separate
 * causes, fixed here: the unit was a bare noun (`RISK`) doing a scale's job, and
 * nothing anywhere said what produced the number.
 *
 * `happy-dom` performs no layout and zeroes every `getBoundingClientRect()`, so
 * these assert the mechanism — the unit text exists, the count line renders — and
 * not that the ring *looks* like a scale.
 */
describe('RiskGauge states the unit and the basis of the number', () => {
  it('shows the ceiling rather than a bare number', () => {
    render(<RiskGauge score={12} riskLevel="low" riskLabel="Low Risk" anomalyCount={1} />);

    expect(screen.getByText(/\/100/)).not.toBeNull();
  });

  it('never renders a percent sign on the score', () => {
    // The score is an index from summing weighted severities, not a calibrated
    // probability. "%" would assert the latter, and a reader would take it as a
    // likelihood that the post is a scam — a claim this panel cannot support.
    const { container } = render(
      <RiskGauge score={12} riskLevel="low" riskLabel="Low Risk" anomalyCount={1} />
    );

    expect(container.innerHTML).not.toMatch(/>12\s*%|<span[^>]*>12%</);
  });

  it('says what produced the score', () => {
    // The provenance line is the whole point of the change: without it the
    // number has no connection to anything in the reader's own posting.
    render(<RiskGauge score={12} riskLevel="low" riskLabel="Low Risk" anomalyCount={1} />);

    expect(screen.getByText(/1 thing in this post differs from normal/)).not.toBeNull();
  });

  it('pluralises when more than one was reported', () => {
    render(<RiskGauge score={28} riskLevel="low" riskLabel="Low Risk" anomalyCount={3} />);

    expect(screen.getByText(/3 things in this post differ from normal/)).not.toBeNull();
  });

  it('states plainly when nothing stood out', () => {
    render(<RiskGauge score={0} riskLevel="low" riskLabel="Low Risk" anomalyCount={0} />);

    expect(screen.getByText(/Nothing in this post stands out/)).not.toBeNull();
  });

  it('omits the line when the count is unknown rather than claiming zero', () => {
    // "Nothing stands out" is a claim about the posting. Rendering it when the
    // count was never passed would state something the panel cannot support.
    const { container } = render(
      <RiskGauge score={0} riskLevel="low" riskLabel="Low Risk" />
    );

    expect(container.innerHTML).not.toMatch(/Nothing in this post stands out/);
  });

  it('shows the score itself, not a rounded percentage of it', () => {
    // The ring's fill and the number must be the same quantity. They were not:
    // the fill used score/maxScore while the centre rounded it to a percent.
    render(<RiskGauge score={12} riskLevel="low" riskLabel="Low Risk" anomalyCount={1} />);

    expect(screen.getByText('12')).not.toBeNull();
  });
});

describe('RiskGauge ring reads as an instrument', () => {
  it('marks the level boundaries', () => {
    // A ring with no gradations is a progress bar, so its centre number reads
    // as a dial position. Three hairlines at the same thresholds
    // `_level_for` uses — a scale, not invented marks.
    const { container } = render(
      <RiskGauge score={12} riskLevel="low" riskLabel="Low Risk" anomalyCount={1} />
    );

    const ticks = container.querySelectorAll('[data-band]');
    expect(ticks).toHaveLength(3);
    expect(
      Array.from(ticks).map((t) => t.getAttribute('data-band')).sort()
    ).toEqual(['30', '50', '75']);
  });

  it('fills the ring in proportion to the score it displays', () => {
    // dashoffset is circumference * (1 - score/maxScore), so a longer arc must
    // accompany a larger number. Asserted on the attribute rather than pixels.
    const { container } = render(
      <RiskGauge score={75} riskLevel="high" riskLabel="High Risk" anomalyCount={2} />
    );

    const ring = container.querySelector('circle[stroke-dashoffset]');
    const circumference = Number(ring?.getAttribute('stroke-dasharray'));
    const offset = Number(ring?.getAttribute('stroke-dashoffset'));

    // 75 of 100 leaves a quarter of the ring unfilled.
    expect(offset / circumference).toBeCloseTo(0.25, 2);
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

  // ring-breathe peaks at an 11px drop-shadow, so the card border must never
  // cut through the glow. There are two ways to guarantee that, and the two
  // rings use different ones: either the card clips the shadow, or the shadow
  // has room to render before it reaches the border. A ring that does neither
  // lets the border draw a hard line across the glow.
  const glowIsContained = (container: HTMLElement) => {
    const section = container.querySelector('section');
    if (!section) return false;
    if (section.className.includes('overflow-hidden')) return true;

    // Not clipped, so the ring wrapper must reserve room for the shadow.
    const ring = container.querySelector('.ring-pulse')?.closest('.relative');
    return Boolean(ring?.className.match(/\bp-\d\b/));
  };

  it('keeps the scored ring glow from being cut by the card border', () => {
    const { container } = render(<RiskGauge score={75} riskLevel="high" riskLabel="High Risk" />);
    expect(glowIsContained(container)).toBe(true);

    cleanup();
    const moderate = render(<RiskGauge score={45} riskLevel="moderate" riskLabel="Moderate Risk" />);
    expect(glowIsContained(moderate.container)).toBe(true);
  });

  it('keeps the unverified ring glow from being cut by the card border', () => {
    const { container } = render(<RiskGauge score={0} riskLevel="low" unverified />);
    expect(glowIsContained(container)).toBe(true);
  });
});
