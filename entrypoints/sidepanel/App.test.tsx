// The wiring between the two tabs.
//
// `App` had no test, and this feature puts the only behaviour in it that no
// component owns: Open is pressed in Match, and a scan must appear in Scan. If
// the tab flip or the token is wrong, every component test still passes — each
// one only ever saw its own side of the handoff.
//
// Both views are stubbed. That is the point, not a shortcut: this asserts that
// App passes the right thing to each, not what either does with it.

import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react';
import React from 'react';
import type { ScannedJob } from './types';

afterEach(cleanup);

const storedJob: ScannedJob = {
  id: 'job-1',
  title: 'Sales associate wanted',
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
  },
} as unknown as ScannedJob;

vi.mock('./views/ScamScanView', () => ({
  ScamScanView: (props: Record<string, any>) => (
    <div data-role="scan-view" data-token={props.restoredJob?.token ?? ''}>
      <button data-role="fresh-capture" onClick={() => props.onScanStart?.()}>
        fresh
      </button>
    </div>
  ),
}));

vi.mock('./views/ResumeMatchView', () => ({
  ResumeMatchView: (props: Record<string, any>) => (
    <div data-role="match-view" data-visible={String(props.isOnline)}>
      <button data-role="open-job" onClick={() => props.onOpenJob?.(storedJob)}>
        open
      </button>
    </div>
  ),
}));

vi.mock('./hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ isOnline: true, isChecking: false, checkNow: vi.fn() }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  (globalThis as unknown as { chrome: unknown }).chrome = {
    storage: {
      local: {
        get: (_keys: unknown, cb: (r: Record<string, unknown>) => void) =>
          cb({ scannedJobs: [storedJob] }),
        set: vi.fn(),
      },
    },
  };
});

/** Click the Match tab in the side nav, which is not stubbed. */
async function switchToMatch() {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /match/i }));
  });
}

function openFromHistory() {
  return act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'open' }));
  });
}

/**
 * Whether a view's wrapper is on screen.
 *
 * `App` keeps both views mounted and hides the inactive one with a `hidden`
 * class on a plain wrapper div — the stubbed view's own parent. Read from that
 * parent rather than searching ancestors for `hidden`, because `hidden` as a
 * substring also appears in classes that have nothing to do with visibility.
 */
function isVisible(role: 'scan-view' | 'match-view'): boolean {
  const wrapper = document.querySelector(`[data-role="${role}"]`)!.parentElement!;
  return !wrapper.className.split(/\s+/).includes('hidden');
}

describe('opening a scan from the Match tab', () => {
  it('shows it in the Scan tab, marked as saved', async () => {
    const { default: App } = await import('./App');
    render(React.createElement(App));

    // Nothing marked yet: the panel is showing whatever it was showing.
    expect(screen.queryByText('Saved from job history')).toBeNull();

    // Start on Match. `activeView` initialises to `'scan'`, so without this the
    // tab flip is unobservable and deleting `setActiveView('scan')` from
    // `handleOpenJob` would leave every assertion here passing.
    await switchToMatch();
    expect(isVisible('match-view')).toBe(true);
    expect(isVisible('scan-view')).toBe(false);

    await openFromHistory();

    expect(isVisible('scan-view')).toBe(true);
    expect(isVisible('match-view')).toBe(false);
    expect(document.querySelector('[data-role="scan-view"]')!.getAttribute('data-token')).toBe('1');
    expect(screen.getByText('Saved from job history')).toBeTruthy();
  });

  it('gives a second open a new token', async () => {
    // The restore keys on this number, not on the job. A token stuck at 1 means
    // reopening the same job leaves the panel showing the previous result while
    // the reader believes they just reloaded it — so this asserts the counter
    // moves, not that the panel changed.
    const { default: App } = await import('./App');
    render(React.createElement(App));

    await openFromHistory();
    expect(document.querySelector('[data-role="scan-view"]')!.getAttribute('data-token')).toBe('1');

    await openFromHistory();
    expect(document.querySelector('[data-role="scan-view"]')!.getAttribute('data-token')).toBe('2');
  });

  it('clears the marker when the reader takes a fresh capture', async () => {
    // The marker claims the panel is showing stored evidence. Left standing
    // across a new capture it would be claiming that about results that are
    // seconds old.
    const { default: App } = await import('./App');
    render(React.createElement(App));

    await openFromHistory();
    expect(screen.queryByText('Saved from job history')).toBeTruthy();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'fresh' }));
    });

    expect(screen.queryByText('Saved from job history')).toBeNull();
  });
});