import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup, screen } from '@testing-library/react';
import React from 'react';
import { TopAppBar } from './TopAppBar';
import { formatTimestamp } from '../../lib/format';

afterEach(() => cleanup());

/**
 * The app bar has to say the panel is showing a stored scan.
 *
 * A reopened scan looks exactly like a fresh one, which is what was asked for,
 * and that is the problem: the Scan button still reads "Pick again" and the
 * findings still read as current. The date is what resolves it — evidence
 * retrieved four days ago was retrieved four days ago.
 *
 * What the marker must not do is claim a fresh scan is saved. An always-on
 * marker would be worse than none.
 */
describe('a reopened scan in the app bar', () => {
  const timestamp = '2026-10-09T08:30:00.000Z';

  it('says where this scan came from, and the day it was taken', () => {
    render(
      React.createElement(TopAppBar, {
        savedScan: { title: 'Sales associate wanted', timestamp },
      }),
    );

    expect(screen.getByText('Saved from job history')).toBeTruthy();
    // One formatter, shared with the history rows, so a row and this marker
    // cannot show two different dates for one scan.
    expect(screen.getByText(formatTimestamp(timestamp))).toBeTruthy();
  });

  it('says nothing extra when no saved scan is open', () => {
    render(React.createElement(TopAppBar, {}));

    expect(screen.queryByText('Saved from job history')).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
  });
});