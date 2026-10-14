/**
 * The anomalies column must not push the panel wider than the panel is.
 *
 * `happy-dom` performs no flex layout and zeroes every `getBoundingClientRect`,
 * so the rendered width of these elements cannot be asserted here. What can be
 * asserted is the class that produces the behaviour, which is the same approach
 * the FLIP and ring-glow tests take. If a rule below is removed, this test fails;
 * whether the browser then overflows is left to a human with a narrow panel.
 *
 * The root cause is flexbox defaults, not a missing width. A flex item's
 * `min-width` is `auto`, which means it refuses to shrink below the intrinsic
 * min-content width of its contents. A long anomaly title, or one long unbroken
 * word, therefore sets a floor the container cannot compress â€” and the panel
 * scrolls sideways instead of wrapping. `min-w-0` is what permits the shrink;
 * `shrink-0` on a chip keeps it from being crushed while the text around it
 * gives way.
 */
import { afterEach, describe, it, expect } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AnomaliesList } from './AnomaliesList';

// Without this, a second render() in the same file leaves the first tree in the
// document and every getByText finds two matches.
afterEach(() => {
  cleanup();
});

const LONG_TITLE =
  'Requests applicants to send an advance payment through a personal bank account before starting work';

function anomaly(over: Partial<Parameters<typeof AnomaliesList>[0]['anomalies'][number]> = {}) {
  return {
    id: 'a1',
    icon: 'flag' as const,
    title: LONG_TITLE,
    description:
      'The posting asks the applicant to pay a processing fee before the first shift, which no legitimate employer does.',
    severity: 'high' as const,
    ...over,
  };
}

describe('AnomaliesList at a narrow panel width', () => {
  it('lets the heading row shrink instead of overflowing', () => {
    render(<AnomaliesList anomalies={[anomaly()]} critical />);

    const heading = screen.getByRole('heading', { name: /Anomalies \(1\)/ });
    // The group holding the icon and the heading is the left half of a
    // justify-between row; without min-w-0 it cannot compress.
    expect(heading.parentElement!.className).toContain('min-w-0');
  });

  it('keeps the HIGH SEVERITY badge at full size', () => {
    render(<AnomaliesList anomalies={[anomaly()]} critical />);

    const badge = screen.getByText('HIGH SEVERITY');
    // The opposite requirement: the badge must not be the thing that gives way.
    expect(badge.className).toContain('shrink-0');
  });

  it('lets a long anomaly title compress rather than widen the card', () => {
    render(<AnomaliesList anomalies={[anomaly()]} critical />);

    const title = screen.getByRole('heading', { name: LONG_TITLE });
    // The text column is a flex child of the card. min-w-0 is what allows it
    // below its min-content width; without it the card is as wide as the title.
    expect(title.parentElement!.parentElement!.className).toContain('min-w-0');
  });

  it('keeps the severity chip from being crushed by a long title', () => {
    render(<AnomaliesList anomalies={[anomaly({ severity: 'mid' })]} critical={false} />);

    const chip = screen.getByText('mid');
    expect(chip.className).toContain('shrink-0');
  });
});
