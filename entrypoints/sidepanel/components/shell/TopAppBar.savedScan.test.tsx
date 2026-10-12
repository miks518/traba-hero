import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, cleanup, screen, act } from '@testing-library/react';
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

/** Capture the observer TopAppBar installs, so a test can report a width. */
let observers: Array<(entries: Array<{ contentRect: { width: number } }>) => void> = [];

beforeEach(() => {
  observers = [];
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    constructor(cb: (e: Array<{ contentRect: { width: number } }>) => void) {
      observers.push(cb);
    }
    observe() {}
    disconnect() {}
  };
});

/** Report a bar width, as a real drag of the side panel's edge would. */
async function resizeBarTo(width: number) {
  await act(async () => {
    observers.forEach((cb) => cb([{ contentRect: { width } }]));
  });
}

function renderBar(savedScan?: { title: string; timestamp: string }) {
  return render(React.createElement(TopAppBar, savedScan ? { savedScan } : {}));
}

describe('a reopened scan in the app bar', () => {
  const timestamp = '2026-10-09T08:30:00.000Z';

  it('says where this scan came from, and the day it was taken', () => {
    renderBar({ title: 'Sales associate wanted', timestamp });

    expect(screen.getByText('Saved from job history')).toBeTruthy();
    // One formatter, shared with the history rows, so a row and this marker
    // cannot show two different dates for one scan.
    expect(screen.getByText(formatTimestamp(timestamp))).toBeTruthy();
  });

  it('says nothing extra when no saved scan is open', () => {
    renderBar();

    expect(screen.queryByText('Saved from job history')).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('keeps the words while the bar is wide enough for them', async () => {
    renderBar({ title: 'Sales associate wanted', timestamp });
    await resizeBarTo(520);

    expect(screen.getByText('Saved from job history')).toBeTruthy();
  });

  it('keeps only the date once the bar is too narrow for the words', async () => {
    // A side panel can be dragged down to roughly 320px. At that width the
    // marker's words push the text-size and help controls off the bar or over
    // them, and the words are the part that can go: the date is what tells the
    // reader this is stored rather than current.
    renderBar({ title: 'Sales associate wanted', timestamp });
    await resizeBarTo(340);

    expect(screen.queryByText('Saved from job history')).toBeNull();
    expect(screen.getByText(formatTimestamp(timestamp))).toBeTruthy();
  });

  it('does not shrink the logo as the bar narrows', () => {
    // The logo is an inline SVG in a flex row, so it is a flex item and shrinks
    // like one. It is a fixed-width mark, not text that can usefully truncate,
    // and a logo that changes size with the panel looks like a rendering bug.
    const { container } = renderBar({ title: 'Sales associate wanted', timestamp });

    const logo = container.querySelector('svg')!;
    expect(logo.className.split(/\s+/)).toContain('shrink-0');
  });

  it('keeps the bar controls out of the marker space', () => {
    // The row holding text size, help and theme. It is fixed-content, so it
    // must not be a flex item that shrinks — otherwise the marker wins the
    // space and the controls end up underneath it.
    const { container } = renderBar({ title: 'Sales associate wanted', timestamp });

    const actions = container.querySelector('[data-role="app-bar-actions"]')!;
    expect(actions.className.split(/\s+/)).toContain('shrink-0');
  });

  it('sets the date in the same font as the words beside it', () => {
    // It was set in a monospace face while the words beside it were in the
    // label face. Same size, same family: the date is part of that sentence.
    const { container } = renderBar({ title: 'Sales associate wanted', timestamp });

    const date = screen.getByText(formatTimestamp(timestamp));
    expect(date.className).not.toContain('font-mono');
  });
});