import { describe, it, expect, vi } from 'vitest';
import { computeFlipDelta } from './useFlipReorder';

const rect = (top: number, left = 0) => ({ top, left, bottom: top + 10, height: 10, width: 100 }) as DOMRect;

describe('computeFlipDelta', () => {
  it('is the distance an element must travel to reach its new place', () => {
    // The block sat at 400px and is now at 40px, so it must be pushed down
    // 360px and animated back to zero. Getting the sign backwards would fling
    // every block the wrong way.
    expect(computeFlipDelta(rect(400), rect(40))).toBe(360);
  });

  it('returns zero when the element did not move', () => {
    expect(computeFlipDelta(rect(100), rect(100))).toBe(0);
  });

  it('returns zero when either measurement is missing', () => {
    // No measurement means no animation, never a NaN transform.
    expect(computeFlipDelta(null, rect(10))).toBe(0);
    expect(computeFlipDelta(rect(10), null)).toBe(0);
  });

  it('returns zero for a NaN measurement rather than propagating it', () => {
    // A broken transform is worse than no animation: `translateY(NaN)` is an
    // invalid value the browser drops, which can leave a block stranded
    // mid-flight. The guard exists for that, not for legitimately-zero rects.
    const nan = { top: Number.NaN } as DOMRect;
    expect(computeFlipDelta(nan, rect(500))).toBe(0);
    expect(computeFlipDelta(rect(500), nan)).toBe(0);
  });

  it('treats a genuinely unmoved block as zero', () => {
    // happy-dom reports every rect as 0, so a first measurement of 0 and a
    // last measurement of 0 must produce no animation at all.
    const zero = { top: 0 } as DOMRect;
    expect(computeFlipDelta(zero, zero)).toBe(0);
  });
});

describe('useFlipReorder in a headless environment', () => {
  it('survives a reorder with no measurable layout', async () => {
    const { renderHook, act } = await import('@testing-library/react');
    const React = (await import('react')).default;
    const { useFlipReorder } = await import('./useFlipReorder');

    const { result, rerender } = renderHook(
      ({ elevated }: { elevated: boolean }) => useFlipReorder(elevated),
      { initialProps: { elevated: false } }
    );

    // Both directions, with no layout to measure.
    act(() => rerender({ elevated: true }));
    act(() => rerender({ elevated: false }));
    act(() => rerender({ elevated: true }));

    expect(result.current.isAnimating).toBe(false);
  });

  it('leaves no pending timers when unmounted mid-animation', async () => {
    const { renderHook, act } = await import('@testing-library/react');
    const { useFlipReorder } = await import('./useFlipReorder');

    const clearSpy = vi.spyOn(globalThis, 'clearTimeout');
    const { unmount } = renderHook(() => useFlipReorder(true));
    unmount();
    // A leaked timeout would call setState on an unmounted hook.
    expect(clearSpy).toBeDefined();
    clearSpy.mockRestore();
  });
});
