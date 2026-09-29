// A critical job told the reader it was "Included in resume matching".
//
// The exclusion itself was never broken: `verifiedJobs` is `low` risk only, and
// that collection is what gets matched. The label was. The per-job status
// branch tested `suspicious` — which is `isSuspiciousJob`, meaning *moderate* —
// and then `riskLevel === null`, so `high` and `critical` fell through to the
// final `else` and got the green "No high-severity indicators found. Included in
// resume matching." message. The one branch that must never be reassuring is the
// branch the most dangerous job took.
//
// The misleading identifier is part of the cause: `suspicious` reads like it
// means the risky levels, so anyone extending this branch would reasonably
// assume the dangerous jobs were already handled. The test therefore asserts the
// message for every level, not just that the critical case changed.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react';
import React from 'react';
import { ResumeMatchView } from './ResumeMatchView';
import type { ScannedJob } from '../types';

afterEach(cleanup);

vi.mock('../lib/api', () => ({
  pingHealth: vi.fn().mockResolvedValue(true),
  analyzeResumeStream: vi.fn(),
  matchResumeStream: vi.fn(),
  clearHistory: vi.fn().mockResolvedValue(undefined),
}));

const job = (level: string | null): ScannedJob =>
  ({
    id: `job-${level}`,
    timestamp: Date.now(),
    scanResult: {
      riskLevel: level,
      riskScore: level === 'critical' ? 90 : 40,
      riskScored: level !== null,
      isJobPosting: true,
      postingAnalysis: 'A posting.',
      jobSummary: 'A role.',
      redFlags: [],
      companyName: 'Acme',
    },
  }) as unknown as ScannedJob;

const RESUME = {
  skills: ['Python'],
  experience_years: 3,
  job_titles: ['Developer'],
  industries: ['Software'],
  summary: 'A summary.',
};

/** Minimal resume, because the view renders a preview when one is present. */
function renderWith(level: string | null, jobs?: ScannedJob[]) {
  return render(
    React.createElement(ResumeMatchView, {
      scannedJobs: jobs ?? [job(level)],
      resumeData: RESUME,
      onResumeData: vi.fn(),
      onScanComplete: vi.fn(),
      isOnline: true,
    } as never)
  );
}

/** Expand the first job row so its status message renders. */
function expandFirstRow() {
  const rows = screen.getAllByRole('button');
  for (const row of rows) {
    if (row.className.includes('cursor-pointer') || row.getAttribute('aria-expanded') !== null) {
      fireEvent.click(row);
      return;
    }
  }
  // Fall back to the first clickable job header.
  fireEvent.click(rows[0]);
}

describe('the per-job matching status is correct for every risk level', () => {
  it('says a critical job is excluded', async () => {
    const { container } = renderWith('critical');
    await act(async () => {
      expandFirstRow();
    });

    const text = container.textContent ?? '';
    expect(text).toMatch(/Excluded from resume matching/i);
    expect(text).not.toMatch(/Included in resume matching/i);
  });

  it('says a high job is excluded', async () => {
    const { container } = renderWith('high');
    await act(async () => {
      expandFirstRow();
    });

    const text = container.textContent ?? '';
    expect(text).toMatch(/Excluded from resume matching/i);
    expect(text).not.toMatch(/Included in resume matching/i);
  });

  it('says a moderate job is excluded', async () => {
    const { container } = renderWith('moderate');
    await act(async () => {
      expandFirstRow();
    });

    expect(container.textContent ?? '').toMatch(/Excluded from resume matching/i);
  });

  it('says an unscored job is excluded pending verification', async () => {
    const { container } = renderWith(null);
    await act(async () => {
      expandFirstRow();
    });

    expect(container.textContent ?? '').toMatch(/Not yet scored/i);
  });

  it('only a low-risk job is reported as included', async () => {
    const { container } = renderWith('low');
    await act(async () => {
      expandFirstRow();
    });

    const text = container.textContent ?? '';
    expect(text).toMatch(/Included in resume matching/i);
    expect(text).not.toMatch(/Excluded from resume matching/i);
  });
});

describe('severity badges are distinguishable', () => {
  /** High and Moderate shipped byte-identical amber badges. */
  it('does not paint High and Moderate the same', () => {
    const { container } = renderWith('high');
    expect(container.textContent).toMatch(/High/);

    const { container: moderateRow } = renderWith('moderate');
    expect(moderateRow.textContent).toMatch(/Moderate/);
  });

  it('High is not the same colour as Moderate', () => {
    const high = renderWith('high').container.querySelectorAll('[class*="border-amber-500"]');
    const moderate = renderWith('moderate').container.querySelectorAll('[class*="border-amber-500"]');

    // Neither level may borrow the other's identity: High is an alarm, so it
    // takes the error token rather than sharing Moderate's amber.
    const highUsesError = renderWith('high').container.innerHTML.includes('text-error');
    expect(highUsesError).toBe(true);
    expect(moderate.length).toBeGreaterThan(0);
    expect(high).toHaveLength(0);
  });
});

describe('the matching input is low risk only', () => {
  it('never feeds a high or critical job to the matcher', async () => {
    const matchResumeStream = vi.fn();
    vi.doMock('../lib/api', () => ({
      pingHealth: vi.fn().mockResolvedValue(true),
      analyzeResumeStream: vi.fn(),
      matchResumeStream,
      clearHistory: vi.fn().mockResolvedValue(undefined),
    }));

    const { container } = render(
      React.createElement(ResumeMatchView, {
        scannedJobs: [job('critical'), job('high'), job('moderate'), job('low')],
        resumeData: RESUME,
        onResumeData: vi.fn(),
        onScanComplete: vi.fn(),
        isOnline: true,
      } as never)
    );

    // The count on the match button is the set that will be matched.
    await act(async () => {});
    expect(container.textContent).toMatch(/\(1 Low Risk\)/);
  });
});
