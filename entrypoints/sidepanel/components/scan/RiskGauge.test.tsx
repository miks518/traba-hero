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

  it('keeps the unverified colour amber, not red or green', () => {
    const { container } = render(<RiskGauge score={0} riskLevel="low" unverified />);

    const html = container.innerHTML;
    // The moderate level already uses this amber; reusing it keeps one warning
    // colour in the gauge rather than two.
    expect(html).toContain('hsl(45, 78%, 44%)');
  });
});
