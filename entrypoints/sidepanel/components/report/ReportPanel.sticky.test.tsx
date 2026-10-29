// The pinned assessment.
//
// happy-dom performs no layout, so "stays while the report scrolls" cannot be
// observed here — there is no scrolling. What can be held is the class
// contract that produces the pinning: the banner sits in a wrapper that is
// sticky at the top of the panel's scrollport, layered above the cards that
// slide under it, and painted in the page background so the wrapper's own box
// is invisible while it masks the banner's rounded corners. Deleting any of
// those classes fails these tests; so does moving the banner out of the
// wrapper.

import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import React from 'react';
import { ReportPanel } from './ReportPanel';
import type { ScanResult } from '../../types';

afterEach(cleanup);

const result = {
  isJobPosting: true,
  assessment: 'red',
  assessed: true,
  companyName: 'Acme Trading',
  anomalies: [],
  flagsCritical: false,
  verificationLoading: false,
  offerAnalysisLoading: false,
  verificationError: false,
} as unknown as ScanResult;

function renderPanel() {
  return render(
    React.createElement(ReportPanel, {
      result,
      verifying: false,
      verificationError: false,
      currentQuery: '',
      assessmentReason: 'The post asks for payment before hiring.',
      timestamp: '2026-10-09T08:30:00.000Z',
      title: 'Sales associate wanted',
      needsCompanyName: false,
      elevate: false,
    }),
  );
}

describe('the assessment banner pins while the report scrolls', () => {
  it('sits in a sticky wrapper at the top of the scrollport', () => {
    const { container } = renderPanel();

    const block = container.querySelector('[data-role="assessment-block"]')!;
    const pinned = block.closest('.sticky')!;
    expect(pinned).toBeTruthy();
    expect(pinned.className).toContain('top-0');
    // Below the action bar (z-30) and the overlays, above the report cards
    // sliding under the pinned banner.
    expect(pinned.className).toContain('z-20');
    // Opaque page background: the wrapper is invisible at rest and masks the
    // banner's rounded corners once content scrolls beneath it.
    expect(pinned.className).toContain('bg-background');
  });

  it('pins inside the report, not as a floating layer', () => {
    const { container } = renderPanel();

    const pinned = container.querySelector('[data-role="assessment-block"]')!.closest('.sticky')!;
    expect(pinned.closest('[data-role="report-panel"]')).toBeTruthy();
  });

  it('pins only the assessment; the subject line scrolls away with it', () => {
    const { container } = renderPanel();

    const meta = container.querySelector('[data-role="job-meta"]')!;
    expect(meta.closest('.sticky')).toBeNull();
  });
});
