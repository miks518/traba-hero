import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const pingHealth = vi.fn<() => Promise<boolean>>();

vi.mock('../lib/api', () => ({
  pingHealth: (...args: unknown[]) => pingHealth(...(args as [])),
}));

import { useBackendHealth } from './useBackendHealth';

const POLL_INTERVAL_MS = 4000;

function Probe({ onChange }: { onChange: (isOnline: boolean) => void }) {
  const { isOnline } = useBackendHealth();
  onChange(isOnline);
  return <span data-testid="state">{isOnline ? 'online' : 'offline'}</span>;
}

async function tick(times: number) {
  for (let i = 0; i < times; i += 1) {
    await act(async () => {
      vi.advanceTimersByTime(POLL_INTERVAL_MS);
    });
  }
}

beforeEach(() => {
  pingHealth.mockReset();
  pingHealth.mockResolvedValue(true);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('useBackendHealth', () => {
  it('starts optimistic and stays online while the backend answers', async () => {
    vi.useFakeTimers();
    render(<Probe onChange={() => undefined} />);

    expect(screen.getByTestId('state').textContent).toBe('online');

    await tick(3);

    expect(pingHealth).toHaveBeenCalled();
    expect(screen.getByTestId('state').textContent).toBe('online');
  });

  it('survives a single failed probe without flipping offline', async () => {
    vi.useFakeTimers();
    pingHealth.mockResolvedValueOnce(true);
    render(<Probe onChange={() => undefined} />);

    await tick(1);
    pingHealth.mockResolvedValueOnce(false);
    await tick(1);

    expect(screen.getByTestId('state').textContent).toBe('online');
  });

  it('flips offline after two consecutive failed probes', async () => {
    vi.useFakeTimers();
    pingHealth.mockResolvedValueOnce(true);
    render(<Probe onChange={() => undefined} />);

    await tick(1);
    pingHealth.mockResolvedValue(false);
    await tick(2);

    expect(screen.getByTestId('state').textContent).toBe('offline');
  });

  it('recovers on the first successful probe', async () => {
    vi.useFakeTimers();
    pingHealth.mockResolvedValue(false);
    render(<Probe onChange={() => undefined} />);

    await tick(2);
    expect(screen.getByTestId('state').textContent).toBe('offline');

    pingHealth.mockResolvedValue(true);
    await tick(1);

    expect(screen.getByTestId('state').textContent).toBe('online');
  });

  it('requires a fresh pair of failures to trip again after recovery', async () => {
    vi.useFakeTimers();
    pingHealth.mockResolvedValue(false);
    render(<Probe onChange={() => undefined} />);

    await tick(2);
    pingHealth.mockResolvedValue(true);
    await tick(1);
    pingHealth.mockResolvedValue(false);
    await tick(1);

    expect(screen.getByTestId('state').textContent).toBe('online');
  });

  it('stops polling after unmount', async () => {
    vi.useFakeTimers();
    const { unmount } = render(<Probe onChange={() => undefined} />);

    await tick(1);
    const callsBefore = pingHealth.mock.calls.length;

    unmount();
    await tick(3);

    expect(pingHealth.mock.calls.length).toBe(callsBefore);
  });
});
