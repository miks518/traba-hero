// Two things about the Match tab that a reader hits before any scan.
//
// The upload sits below the history list, so getting to it means scrolling past
// every job that has been scanned — and with the list capped at twenty, that is
// a long way down. The two branches of the resume section never coexist: with no
// resume there is an uploader, with one there is a preview and a Match button.
// Only the uploader moves, so a reader who already uploaded a resume sees the
// tab arranged exactly as before.
//
// The limit is stated, not merely enforced. A list that silently drops the
// oldest scan is a list a reader stops trusting — "where did that one go" is
// the natural question and this product is asking people to rely on what it
// kept.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import React from 'react';
import { ResumeMatchView } from './ResumeMatchView';
import { MAX_SCAN_HISTORY } from '../lib/scanHistory';
import type { ScannedJob } from '../types';

afterEach(cleanup);

vi.mock('../lib/api', () => ({
  pingHealth: vi.fn().mockResolvedValue(true),
  analyzeResumeStream: vi.fn(),
  matchResumeStream: vi.fn(),
  clearHistory: vi.fn().mockResolvedValue(undefined),
}));

const RESUME = {
  skills: ['Python'],
  experience_years: 3,
  job_titles: ['Developer'],
  industries: ['Software'],
  summary: 'A summary.',
};

const jobs = Array.from(
  { length: MAX_SCAN_HISTORY },
  (_, i) =>
    ({
      id: `job-${i}`,
      title: `Posting ${i}`,
      summary: '',
      timestamp: '2026-10-09T08:30:00.000Z',
      scanResult: {
        riskLevel: 'low',
        riskLabel: 'Low Risk',
        riskScored: true,
        riskScore: 12,
        riskDescription: '',
        scanningTarget: 'Scanned Element',
        anomalies: [],
        flagsCritical: false,
        isJobPosting: true,
        companyName: 'Acme',
      },
    }) as unknown as ScannedJob,
);

function renderMatch(withResume: boolean) {
  return render(
    React.createElement(ResumeMatchView, {
      scannedJobs: jobs,
      resumeData: withResume ? RESUME : null,
      onResumeData: vi.fn(),
      onClearResume: vi.fn(),
      onClearJobs: vi.fn(),
      isOnline: true,
    } as never),
  );
}

/** Whether `a` comes before `b` in the rendered document. */
function comesBefore(a: Element, b: Element): boolean {
  return Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
}

describe('reaching the resume upload', () => {
  it('puts the uploader above the history list', () => {
    renderMatch(false);

    // A clickable dashed box, not a button — it wraps a hidden file input.
    const uploader = screen.getByText('Upload your resume');
    const heading = screen.getByText('Job Post History');

    expect(comesBefore(uploader, heading)).toBe(true);
  });

  it('leaves a reader who already uploaded their resume where it was', () => {
    // The preview and the Match button are one unit with the match results
    // below them. Lifting the uploader alone moves nothing for this reader,
    // rather than separating a button from what it acts on.
    renderMatch(true);

    expect(screen.queryByText('Upload your resume')).toBeNull();
    const preview = screen.getByTitle('Remove resume');
    expect(comesBefore(screen.getByText('Job Post History'), preview)).toBe(true);
  });
});

describe('the length of scan history', () => {
  it('says how many are kept and what happens to the rest', () => {
    renderMatch(false);

    expect(
      screen.getByText(new RegExp(`${MAX_SCAN_HISTORY} most recent scans`, 'i')),
    ).toBeTruthy();
    expect(
      screen.getByText(/oldest one is deleted automatically/i),
    ).toBeTruthy();
  });

  it('states the limit before it has ever been reached', () => {
    // Stated on an empty history too, deliberately. The reader decides how to
    // use the tab on the first visit, and a notice that only appears once the
    // twentieth scan has been taken is a notice about a loss that has already
    // happened and can no longer be acted on.
    const { container } = render(
      React.createElement(ResumeMatchView, {
        scannedJobs: [],
        resumeData: null,
        onResumeData: vi.fn(),
        onClearResume: vi.fn(),
        onClearJobs: vi.fn(),
        isOnline: true,
      } as never),
    );

    expect(
      container.textContent,
    ).toMatch(new RegExp(`${MAX_SCAN_HISTORY} most recent scans`, 'i'));
  });
});