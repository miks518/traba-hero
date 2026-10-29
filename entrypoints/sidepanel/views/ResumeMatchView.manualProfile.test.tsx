// The manual entry path, as the Match tab offers it.
//
// The form is a second door next to the uploader, not a replacement: with no
// resume the reader sees both, and a saved profile — from either door — takes
// the whole section over. The view's own job is small on purpose: toggle the
// form, hand the built profile up, and say it saved.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react';
import React from 'react';
import { ResumeMatchView } from './ResumeMatchView';
import type { ResumeData, ScannedJob } from '../types';

afterEach(cleanup);

vi.mock('../lib/api', () => ({
  analyzeResumeStream: vi.fn().mockResolvedValue({ data: undefined }),
  matchResumeToJobsStream: vi.fn().mockResolvedValue({ data: undefined }),
}));

const RESUME: ResumeData = {
  skills: ['Python'],
  experience_years: 3,
  job_titles: ['Developer'],
  industries: ['Software'],
  summary: 'A summary.',
};

const jobs: ScannedJob[] = [];

function renderMatch(resumeData: ResumeData | null, onResumeData = vi.fn()) {
  render(
    React.createElement(ResumeMatchView, {
      scannedJobs: jobs,
      resumeData,
      onResumeData,
      onClearResume: vi.fn(),
      onClearJobs: vi.fn(),
      isOnline: true,
    } as never),
  );
  return onResumeData;
}

describe('offering manual entry beside the uploader', () => {
  it('offers the toggle when there is no profile yet, with the form collapsed', () => {
    renderMatch(null);

    expect(screen.getByRole('button', { name: /enter your skills manually/i })).toBeTruthy();
    expect(screen.queryByLabelText(/your skills/i)).toBeNull();
  });

  it('reveals the form on toggle and hands the built profile up, saying it saved', async () => {
    const onResumeData = renderMatch(null);

    fireEvent.click(screen.getByRole('button', { name: /enter your skills manually/i }));
    expect(screen.getByLabelText(/your skills/i)).toBeTruthy();

    fireEvent.change(screen.getByLabelText(/your skills/i), {
      target: { value: 'Excel, BPO' },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /save profile/i }));
    });

    expect(onResumeData).toHaveBeenCalledTimes(1);
    expect(onResumeData).toHaveBeenCalledWith({
      skills: ['Excel', 'BPO'],
      experience_years: 0,
      job_titles: [],
      industries: [],
      summary: '',
      source: 'manual',
    });
    expect(screen.getByText(/profile saved/i)).toBeTruthy();
  });

  it('takes the manual entry away once a profile exists', () => {
    renderMatch(RESUME);

    expect(screen.queryByRole('button', { name: /enter your skills manually/i })).toBeNull();
    expect(screen.queryByLabelText(/your skills/i)).toBeNull();
  });
});
