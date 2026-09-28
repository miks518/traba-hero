import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

/**
 * FLIP: animate blocks that change position rather than jumping to their new
 * place.
 *
 * First, Last, Invert, Play. Measure where each block is, let the reorder
 * happen, measure again, apply the inverse offset so the block appears not to
 * have moved, then animate that offset away. The reader's eye follows the
 * content instead of having it teleport.
 *
 * The alternative — a fade — cannot express a reorder at all: the blocks would
 * dissolve and reappear somewhere else, which reads as a glitch rather than a
 * change of emphasis.
 *
 * Reordering by moving JSX would unmount the blocks, and an unmounted block has
 * nothing to animate and loses its state. So the caller keeps both orderings
 * mounted and passes this the flag that selects which one is visible; the
 * animation is about position, not about the DOM order of a single list.
 */
export const FLIP_DURATION_MS = 350;

/**
 * How far an element has to travel to get from where it was to where it now
 * is. Returns 0 rather than NaN whenever a measurement is missing, so a
 * headless or unmounted environment snaps instead of writing a broken
 * transform.
 */
export function computeFlipDelta(
  first: Pick<DOMRect, 'top'> | null,
  last: Pick<DOMRect, 'top'> | null,
): number {
  if (!first || !last) return 0;
  const delta = first.top - last.top;
  return Number.isFinite(delta) ? delta : 0;
}

export interface FlipReorder {
  /** Register a block and get the ref to spread on it. */
  register: (key: string) => (node: HTMLElement | null) => void;
  /**
   * True while blocks are travelling. The hook writes the transform and the
   * transition imperatively rather than through props, so the only way to see
   * this is to read it — and the styles it writes are already cleaned up by
   * the timer, which means the state is genuinely only for observation.
   */
  isAnimating: boolean;
}

export function useFlipReorder(deps: unknown): FlipReorder {
  const nodes = useRef(new Map<string, HTMLElement>());
  const firstTops = useRef(new Map<string, number>());
  const [isAnimating, setIsAnimating] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const register = useCallback((key: string) => (node: HTMLElement | null) => {
    if (node) nodes.current.set(key, node);
    else nodes.current.delete(key);
  }, []);

  /**
   * Recorded during render, before React mutates the DOM. A layout effect runs
   * *after* the mutation and would only ever see the new positions, which is
   * the "First" measurement gone.
   */
  const recordFirst = useCallback(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    firstTops.current.clear();
    for (const [key, node] of nodes.current) {
      if (node.isConnected) firstTops.current.set(key, node.getBoundingClientRect().top);
    }
  }, []);

  useLayoutEffect(() => {
    recordFirst();
  });

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const moved: { node: HTMLElement; delta: number }[] = [];
    for (const [key, node] of nodes.current) {
      if (!node.isConnected) continue;
      const delta = computeFlipDelta(
        firstTops.current.has(key) ? { top: firstTops.current.get(key)! } : null,
        node.getBoundingClientRect()
      );
      if (delta !== 0) moved.push({ node, delta });
    }
    firstTops.current.clear();
    if (!moved.length) return;

    // Invert: place each block back where it started, without a transition,
    // then Play by clearing the offset on the next frame.
    for (const { node, delta } of moved) {
      node.style.transition = 'none';
      node.style.transform = `translateY(${delta}px)`;
    }
    setIsAnimating(true);

    const raf = requestAnimationFrame(() => {
      for (const { node } of moved) {
        node.style.transition = `transform ${FLIP_DURATION_MS}ms cubic-bezier(0.2, 0, 0, 1)`;
        node.style.transform = '';
      }
    });

    timer.current = setTimeout(() => {
      for (const { node } of moved) {
        node.style.transition = '';
        node.style.transform = '';
      }
      setIsAnimating(false);
    }, FLIP_DURATION_MS);

    return () => {
      cancelAnimationFrame(raf);
      if (timer.current) clearTimeout(timer.current);
    };
  }, [deps]);

  return { register, isAnimating };
}
