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
// message for every assessment, not just that the critical case changed.

import { describe, it, expect, afterEach, vi } from 'vitest';import { render, screen, cleanup, fireEvent, act } from '@testing-library/react';
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

const job = (assessment: string | null): ScannedJob =>
  ({
    id: `job-${assessment}`,
    timestamp: Date.now(),
    scanResult: {
      assessment,
      assessed: assessment !== null,
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
function renderWith(assessment: string | null, jobs?: ScannedJob[]) {
  return render(
    React.createElement(ResumeMatchView, {
      scannedJobs: jobs ?? [job(assessment)],
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

describe('the per-job matching status is correct for every assessment', () => {
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

  it('says a note job is included, because the employer was confirmed', async () => {
    // `note` is a prohibited request at an employer the record confirmed, so the
    // reader can go and see the fee on the employer's own site. That is a
    // posting the matcher may use; `caution` and `stop` are not.
    const { container } = renderWith('note');
    await act(async () => {
      expandFirstRow();
    });

    const text = container.textContent ?? '';
    expect(text).toMatch(/Included in resume matching/i);
    expect(text).not.toMatch(/Excluded from resume matching/i);
  });

  it('says an unassessed job is excluded pending verification', async () => {
    const { container } = renderWith(null);
    await act(async () => {
      expandFirstRow();
    });

    expect(container.textContent ?? '').toMatch(/Not yet assessed/i);
  });

  it('says out loud when a assessment word came from the previous procedure', async () => {
    // A stored reading has no request class and no establishment, so its assessment
    // was mapped from the retired level. Showing that word without saying where
    // it came from would present a legacy label as a decision this system made.
    const legacy = job('caution');
    legacy.scanResult.assessmentRecordedUnder = 'previous-procedure';

    const { container } = renderWith('caution', [legacy]);
    await act(async () => {
      expandFirstRow();
    });

    const text = container.textContent ?? '';
    expect(text).toMatch(/carried over from the previous procedure/i);
    expect(text).not.toMatch(/Included in resume matching/i);
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

describe('assessment badges are distinguishable', () => {
  /**
   * The row badge carrying a assessment word — not a filter chip, not a control.
   * Substring, not exact: the icon inside the badge renders its ligature name as
   * text (`gpp_maybeCaution`), and no other span in the row contains the word.
   */
  function badgeFor(container: HTMLElement, label: string): HTMLElement | null {
    const spans = Array.from(container.querySelectorAll('span'));
    return spans.find((s) => s.textContent?.includes(label)) ?? null;
  }

  /** Caution and Note must not share identical badges. */
  it('does not paint Caution and Note the same', () => {
    const { container } = renderWith('caution');
    expect(container.textContent).toMatch(/Caution/);

    const { container: noteRow } = renderWith('note');
    expect(noteRow.textContent).toMatch(/Note/);
  });

  it('Caution wears the caution chip, Note the verified chip', () => {
    // The badge summarises the report banner, whose tone table gives `caution`
    // the caution tone and `note` the verified one (`assessmentCopy.ts`; the same
    // three-tone decision is documented on the assessment tokens in
    // `tailwind.config.js`). Red is `stop`'s alone.
    //
    // This test used to grep the row's innerHTML for `text-error` / `text-green`
    // and passed without either badge carrying those classes: the substrings came
    // from the resume preview's delete button and the Proceed filter chip, so the
    // badges this test names were never the thing asserted. Asserting the badge
    // element's own class is the honest form, and it is what exposed the old
    // dark-theme palette the badges had been wearing.
    const cautionBadge = badgeFor(renderWith('caution').container, 'Caution');
    expect(cautionBadge, 'the caution badge').toBeTruthy();
    expect(cautionBadge!.className).toContain('chip-caution');

    const noteBadge = badgeFor(renderWith('note').container, 'Note');
    expect(noteBadge, 'the note badge').toBeTruthy();
    expect(noteBadge!.className).toContain('chip-verified');
  });
});

describe('the matching input is the matchable assessments', () => {
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

    // The count on the match button is the set that will be matched, and it is
    // the two the reader can act on.
    await act(async () => {});
    expect(container.textContent).toMatch(/\(2\)/);
    expect(container.textContent).not.toMatch(/\(4\)/);
  });
});