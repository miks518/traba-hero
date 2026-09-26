import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { OfflineBanner } from './OfflineBanner';

afterEach(() => {
  cleanup();
});

describe('OfflineBanner', () => {
  it('renders nothing while the backend is reachable', () => {
    const { container } = render(<OfflineBanner isOnline onRetry={() => undefined} />);

    expect(container.innerHTML).toBe('');
    expect(screen.queryByText('Server Unreachable')).toBeNull();
  });

  it('explains the paused state when the backend is unreachable', () => {
    render(<OfflineBanner isOnline={false} />);

    expect(screen.getByText('Server Unreachable')).not.toBeNull();
    expect(screen.getByText(/Scans and matching are paused/)).not.toBeNull();
  });

  it('fires onRetry from the retry button', () => {
    const onRetry = vi.fn();
    render(<OfflineBanner isOnline={false} onRetry={onRetry} />);

    fireEvent.click(screen.getByText('Retry'));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('disables retry while a check is in flight', () => {
    render(<OfflineBanner isOnline={false} isChecking onRetry={() => undefined} />);

    const button = screen.getByText('Retry').closest('button');
    expect(button?.disabled).toBe(true);
  });
});
