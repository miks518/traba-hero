import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import React from 'react';
import { ReportSkeleton } from './ReportSkeleton';

afterEach(cleanup);

/**
 * The initial-scan placeholder.
 *
 * The old loader was a centred circle and a spinner. It said something was
 * happening, not what was coming. This one mirrors the report's slot order, and
 * the assertions here are mostly about what it refuses to draw: a assessment
 * colour, a assessment headline, or a control the panel does not yet ship.
 */
describe('the report skeleton', () => {
  it('mirrors the report rather than the old loader', () => {
    const { container } = render(React.createElement(ReportSkeleton, { progressPercent: 42 }));
    const root = container.querySelector('[data-role="report-skeleton"]');

    expect(root?.getAttribute('aria-busy')).toBe('true');
    expect(root?.getAttribute('aria-label')).toContain('Reading');
    expect(root?.textContent).toContain('Scanning… 42%');
    // More than the old loader's three lines: subject, assessment, actions,
    // findings and details all have a shape.
    expect(root?.querySelectorAll('.animate-pulse').length).toBeGreaterThan(15);
  });

  it('uses grey only, never a assessment colour', () => {
    const { container } = render(React.createElement(ReportSkeleton, { progressPercent: 10 }));
    const root = container.querySelector('[data-role="report-skeleton"]');

    expect(root?.querySelector('.chip-critical')).toBeNull();
    expect(root?.querySelector('.chip-caution')).toBeNull();
    expect(root?.querySelector('.chip-verified')).toBeNull();
    expect(root?.querySelector('.status-card-critical')).toBeNull();
    expect(root?.querySelector('.status-card-caution')).toBeNull();
    // Every block is on the grey container token, and one step lighter than the
    // wells it sits on, or it would disappear into its own background.
    expect(root?.querySelector('.bg-surface-container-high')).toBeTruthy();
    expect(root?.querySelector('.bg-surface-container-highest')).toBeTruthy();
  });

  it('asserts no assessment while the scan is still running', () => {
    const { container } = render(React.createElement(ReportSkeleton, { progressPercent: 0 }));
    const text = container.textContent ?? '';

    expect(text).not.toContain('Do not proceed');
    expect(text).not.toContain('Looks safe');
    expect(text).not.toContain('No assessment');
  });

  it('does not promise slots the report does not ship', () => {
    const { container } = render(React.createElement(ReportSkeleton, { progressPercent: 50 }));
    const text = container.textContent ?? '';

    expect(text).not.toContain('Was this accurate?');
    expect(text).not.toContain('Report this post');
  });

  it('clamps a percentage outside 0–100', () => {
    const high = render(React.createElement(ReportSkeleton, { progressPercent: 150 }));
    expect(high.container.textContent).toContain('100%');

    cleanup();

    const low = render(React.createElement(ReportSkeleton, { progressPercent: -5 }));
    expect(low.container.textContent).toContain('0%');
  });
});
