// The consent gate on the upload path.
//
// The first upload may not send anything until the reader has agreed, and the
// agreement has to come before the network call, not after it. A reader who
// has agreed once sees the plain file confirmation as before — the notice is
// for the decision, not a toll on every visit.

import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, act, waitFor } from '@testing-library/react';
import React from 'react';
import { ResumeMatchView } from './ResumeMatchView';

afterEach(cleanup);

vi.mock('../lib/api', () => ({
  analyzeResumeStream: vi.fn().mockResolvedValue({ data: undefined }),
  matchResumeToJobsStream: vi.fn().mockResolvedValue({ data: undefined }),
}));

import { analyzeResumeStream } from '../lib/api';
import type { Mock } from 'vitest';

const analyzeStreamMock = analyzeResumeStream as unknown as Mock;

function mockStorage(stored: Record<string, unknown> = {}) {
  const storage = {
    get: vi.fn((_keys: unknown, cb: (r: Record<string, unknown>) => void) => cb({ ...stored })),
    set: vi.fn(),
    remove: vi.fn(),
  };
  (globalThis as unknown as { chrome: unknown }).chrome = { storage: { local: storage } };
  return storage;
}

beforeEach(() => {
  vi.clearAllMocks();
  delete (globalThis as unknown as { chrome?: unknown }).chrome;
});

/** Pick a file through the uploader's hidden input, waiting out FileReader. */
async function pickFile() {
  const input = document.querySelector('input[type="file"]')!;
  const file = new File(['resume text'], 'jane_resume.pdf', { type: 'application/pdf' });
  Object.defineProperty(input, 'files', { value: [file], configurable: true });
  await act(async () => {
    fireEvent.change(input);
  });
  await waitFor(() => {
    expect(
      screen.queryByText(/before we process your resume/i) ??
        screen.queryByText(/upload & scan resume\?/i),
    ).toBeTruthy();
  });
}

async function renderView() {
  render(
    React.createElement(ResumeMatchView, {
      scannedJobs: [],
      resumeData: null,
      onResumeData: vi.fn(),
      onClearResume: vi.fn(),
      onClearJobs: vi.fn(),
      isOnline: true,
    } as never),
  );
  // Flush the mount-time consent read: a real reader picks a file seconds
  // after the panel opens, never inside the same tick as the storage get.
  await act(async () => {});
}

describe('the consent gate on the upload path', () => {
  it('asks for consent before anything is sent, and asks nothing of the network', async () => {
    mockStorage({});
    await renderView();

    await pickFile();

    expect(screen.getByText(/before we process your resume/i)).toBeTruthy();
    expect(screen.queryByText(/upload & scan resume\?/i)).toBeNull();
    expect(analyzeStreamMock).not.toHaveBeenCalled();
  });

  it('agreeing records the decision and sends the file', async () => {
    const storage = mockStorage({});
    await renderView();

    await pickFile();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /agree & upload/i }));
    });

    expect(analyzeStreamMock).toHaveBeenCalledTimes(1);
    expect(analyzeStreamMock.mock.calls[0][1]).toBe('pdf');
    expect(storage.set).toHaveBeenCalledWith({ hasConsentedPrivacy: true });
  });

  it('declining keeps the file local and closes the notice', async () => {
    mockStorage({});
    await renderView();

    await pickFile();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /don't upload/i }));
    });

    expect(analyzeStreamMock).not.toHaveBeenCalled();
    expect(screen.queryByText(/before we process your resume/i)).toBeNull();
    expect(screen.getByText('Upload your resume')).toBeTruthy();
  });

  it('a reader who already agreed sees the plain confirmation instead', async () => {
    mockStorage({ hasConsentedPrivacy: true });
    await renderView();

    await pickFile();

    expect(screen.queryByText(/before we process your resume/i)).toBeNull();
    expect(screen.getByText(/upload & scan resume\?/i)).toBeTruthy();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /proceed & scan/i }));
    });
    expect(analyzeStreamMock).toHaveBeenCalledTimes(1);
    expect(analyzeStreamMock.mock.calls[0][1]).toBe('pdf');
  });
});
