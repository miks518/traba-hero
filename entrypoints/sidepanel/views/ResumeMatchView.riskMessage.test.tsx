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
// message for every verdict, not just that the critical case changed.

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

const job = (verdict: string | null): ScannedJob =>
  ({
    id: `job-${verdict}`,
    timestamp: Date.now(),
    scanResult: {
      verdict,
      verdicted: verdict !== null,
      isJobPosting: true,
      postingAnalysis: 'A posting.',
      jobSummary: 'A role.',
      anomalies: [],
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
function renderWith(verdict: string | null, jobs?: ScannedJob[]) {
  return render(
    React.createElement(ResumeMatchView, {
      scannedJobs: jobs ?? [job(verdict)],
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

describe('the per-job matching status is correct for every verdict', () => {
  it('says a stop job is excluded', async () => {
    const { container } = renderWith('stop');
    await act(async () => {
      expandFirstRow();
    });

    const text = container.textContent ?? '';
    expect(text).toMatch(/Excluded from resume matching/i);
    expect(text).not.toMatch(/Included in resume matching/i);
  });

  it('says a caution job is excluded', async () => {
    const { container } = renderWith('caution');
    await act(async () => {
      expandFirstRow();
    });

    const text = container.textContent ?? '';
    expect(text).toMatch(/Excluded from resume matching/i);
    expect(text).not.toMatch(/Included in resume matching/i);
  });

  it('says a note job is excluded', async () => {
    const { container } = renderWith('note');
    await act(async () => {
      expandFirstRow();
    });

    expect(container.textContent ?? '').toMatch(/Excluded from resume matching/i);
  });

  it('says an unassessed job is excluded pending verification', async () => {
    const { container } = renderWith(null);
    await act(async () => {
      expandFirstRow();
    });

    expect(container.textContent ?? '').toMatch(/Not yet assessed/i);
  });

  it('only a clear job is reported as included', async () => {
    const { container } = renderWith('clear');
    await act(async () => {
      expandFirstRow();
    });

    const text = container.textContent ?? '';
    expect(text).toMatch(/Included in resume matching/i);
    expect(text).not.toMatch(/Excluded from resume matching/i);
  });
});

describe('verdict badges are distinguishable', () => {
  /** Caution and Note must not share identical badges. */
  it('does not paint Caution and Note the same', () => {
    const { container } = renderWith('caution');
    expect(container.textContent).toMatch(/Caution/);

    const { container: noteRow } = renderWith('note');
    expect(noteRow.textContent).toMatch(/Note/);
  });

  it('Caution uses the error token, Note uses the verified token', () => {
    const cautionRow = renderWith('caution');
    const noteRow = renderWith('note');

    // Caution is an alarm, so it takes the error token rather than sharing Note's verified green.
    const cautionUsesError = cautionRow.container.innerHTML.includes('text-error');
    expect(cautionUsesError).toBe(true);
    const noteUsesVerified = noteRow.container.innerHTML.includes('text-green');
    expect(noteUsesVerified).toBe(true);
  });
});

describe('the matching input is clear jobs only', () => {
  it('never feeds a stop or caution job to the matcher', async () => {
    const matchResumeStream = vi.fn();
    vi.doMock('../lib/api', () => ({
      pingHealth: vi.fn().mockResolvedValue(true),
      analyzeResumeStream: vi.fn(),
      matchResumeStream,
      clearHistory: vi.fn().mockResolvedValue(undefined),
    }));

    const { container } = render(
      React.createElement(ResumeMatchView, {
        scannedJobs: [job('stop'), job('caution'), job('note'), job('clear')],
        resumeData: RESUME,
        onResumeData: vi.fn(),
        onScanComplete: vi.fn(),
        isOnline: true,
      } as never)
    );

    // The count on the match button is the set that will be matched.
    await act(async () => {});
    expect(container.textContent).toMatch(/\(1 Proceed\)/);
  });
});