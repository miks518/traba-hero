// A scanned job you cannot go back and re-read.
//
// History stored the whole result and there was no way to render it, so the
// findings a scan produced existed only until the panel was reset. The button
// lives on the expandable history row, not in `JobMatchList`: that component
// renders *matches*, so a job scanned and never run through resume matching
// would have had no way back at all.

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

function job(id: string, title: string): ScannedJob {
  return {
    id,
    title,
    summary: 'A role.',
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
      jobSummary: 'A role.',
      postingAnalysis: 'A posting.',
    },
  } as unknown as ScannedJob;
}

const RESUME = {
  skills: ['Python'],
  experience_years: 3,
  job_titles: ['Developer'],
  industries: ['Software'],
  summary: 'A summary.',
};

function renderWith(jobs: ScannedJob[], onOpenJob?: (j: ScannedJob) => void) {
  return render(
    React.createElement(ResumeMatchView, {
      scannedJobs: jobs,
      resumeData: RESUME,
      onResumeData: vi.fn(),
      onClearResume: vi.fn(),
      onClearJobs: vi.fn(),
      onOpenJob,
      isOnline: true,
    } as never),
  );
}

/** Expand the row for `title`, by clicking its header. */
async function expandRow(title: string) {
  const header = screen.getByText(title).closest('[role="button"]');
  await act(async () => {
    fireEvent.click(header!);
  });
}

describe('opening a scan from history', () => {
  it('reports the job whose row was opened', async () => {
    const onOpenJob = vi.fn();
    const first = job('job-1', 'Sales associate wanted');
    renderWith([first, job('job-2', 'Warehouse staff')], onOpenJob);

    await expandRow('Sales associate wanted');
    const open = document.querySelectorAll('[data-role="open-job"]');
    expect(open.length).toBe(1);

    await act(async () => {
      fireEvent.click(open[0]);
    });

    // The whole job, not its id. An id would be enough to look it up again and
    // nothing would catch it here, and it would move the storage read into the
    // caller for no gain.
    expect(onOpenJob).toHaveBeenCalledTimes(1);
    expect(onOpenJob.mock.calls[0][0]).toEqual(first);
  });

  it('offers the button only on a row the reader has opened', async () => {
    // Not a bulk action on the list. A button visible on every row at once
    // reads as something you can do to the whole history, and there is no such
    // thing.
    renderWith(
      [job('job-1', 'Sales associate wanted'), job('job-2', 'Warehouse staff')],
      vi.fn(),
    );

    expect(document.querySelectorAll('[data-role="open-job"]').length).toBe(0);

    await expandRow('Warehouse staff');

    expect(document.querySelectorAll('[data-role="open-job"]').length).toBe(1);
  });
});