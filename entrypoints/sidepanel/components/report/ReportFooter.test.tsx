import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import React from 'react';
import { ReportFooter } from './ReportFooter';

/**
 * The footer states the assessment's limit and nothing else.
 *
 * The ruleset version used to sit here as a build constant. It was dropped
 * because a reader cannot act on it and cannot compare it against anything they
 * hold — the line is now only what the reading can and cannot establish.
 */

afterEach(cleanup);

describe('the report footer', () => {
  it('states the assessment limitation', () => {
    const { container } = render(React.createElement(ReportFooter));

    expect(container.textContent).toContain(
      'This is a risk assessment, not proof of fraud or legitimacy.'
    );
    expect(container.textContent).toContain('A scan can miss a convincing fake.');
  });

  it('does not name a ruleset version', () => {
    const { container } = render(React.createElement(ReportFooter));

    expect(container.textContent).not.toMatch(/ruleset/i);
    expect(container.textContent).not.toMatch(/2026\.10\.2/);
  });

  it('shows the scan id only when one is carried', () => {
    const { container } = render(React.createElement(ReportFooter, { scanId: 'a2f91c' }));

    expect(container.textContent).toContain('Scan a2f91c');
  });
});
