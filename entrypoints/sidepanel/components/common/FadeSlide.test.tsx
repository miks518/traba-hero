import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { ComponentType, ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import * as commonComponents from './index';
import { TopAppBar } from '../shell/TopAppBar';

interface FadeSlideProps {
  show: boolean;
  className?: string;
  children: ReactNode;
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('FadeSlide', () => {
  it('exposes reusable entry and exit behavior', () => {
    vi.useFakeTimers();
    const FadeSlide = (commonComponents as unknown as {
      FadeSlide?: ComponentType<FadeSlideProps>;
    }).FadeSlide;

    expect(FadeSlide).toBeTypeOf('function');
    if (!FadeSlide) return;

    const { rerender } = render(
      <FadeSlide show className="panel">
        <span>Panel</span>
      </FadeSlide>
    );
    const panel = screen.getByText('Panel').parentElement;

    expect(panel?.classList.contains('animate-fade-slide-in')).toBe(true);

    rerender(
      <FadeSlide show={false} className="panel">
        <span>Panel</span>
      </FadeSlide>
    );

    expect(screen.getByText('Panel')).not.toBeNull();
    expect(panel?.getAttribute('aria-hidden')).toBe('true');
    expect(panel?.classList.contains('opacity-0')).toBe(true);

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(screen.queryByText('Panel')).toBeNull();
  });
});

describe('TopAppBar popups', () => {
  it.each([
    ['Text Size', 'text_fields', 'Text Size'],
    ['Help', 'help', 'How to Use Trabahero'],
  ])('starts the %s popup entry animation', (_name, iconName, popupTitle) => {
    render(<TopAppBar onTextSizeChange={() => undefined} />);

    fireEvent.click(screen.getByText(iconName));

    const popup = screen.getByText(popupTitle).parentElement;
    expect(popup?.classList.contains('animate-fade-slide-in')).toBe(true);
  });
});
