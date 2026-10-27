// A money-demand finding's container carried a near-invisible border.
//
// The border style was defined per severity and applied only to the icon
// circle, so the card that actually held the finding had
// `border-outline-variant/10` regardless of what the finding asked for. The
// alarm was communicated entirely by a 32px dot, which is the smallest thing
// on the card. A reader scanning the panel for "which of these asks for money"
// had nothing to scan.
//
// The card now styles by the finding's taxonomy tier (`lib/findingTiers.ts`);
// the scan emits no severity.
//
// This asserts on the class list. `happy-dom` performs no flex layout and zeroes
// every `getBoundingClientRect()`, so a pixel claim cannot be checked here — only
// that the border token the tier already carries reaches the container.

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const source = readFileSync(
  join(process.cwd(), 'entrypoints/sidepanel/components/scan/AnomalyCard.tsx'),
  'utf-8'
);

describe('the anomaly card is outlined by its tier', () => {
  /** The outermost div's className — the card that holds the finding. */
  const containerClass = (): string => {
    const marker = 'className={`bg-surface-container-low';
    const start = source.indexOf(marker);
    expect(start, 'the card container was not found').toBeGreaterThan(-1);
    return source.slice(start, source.indexOf('}`', start) + 2);
  };

  it('applies the tier border to the container, not only the icon', () => {
    // The container is the outermost div; it must carry ${style.border}.
    expect(containerClass()).toMatch(/\$\{style\.border\}/);
  });

  it('no longer leaves the container on a near-invisible neutral border', () => {
    // Scoped to the class list, not the file: a comment explaining what was
    // removed would otherwise match its own description of the old value.
    expect(containerClass()).not.toMatch(/border-outline-variant\/10/);
  });

  it('keeps the tier border on the icon as well', () => {
    // Removing it from the icon would lose the cue on the dot itself.
    const icon = source.slice(
      source.indexOf('${style.bg} ${style.text} h-8 w-8'),
      source.indexOf('>', source.indexOf('${style.bg} ${style.text} h-8 w-8'))
    );
    expect(icon).toMatch(/\$\{style\.border\}/);
  });

  it('still carries the 3D treatment that makes this card the original design', () => {
    // The other containers in the panel are flat. This one predates them and
    // keeps the highlight; that difference is intentional, not drift.
    expect(source).toMatch(/tactile-card/);
  });

  it('still has a distinct border token per tier', () => {
    for (const tier of [3, 2, 1]) {
      expect(source).toMatch(
        new RegExp(`\\b${tier}:\\s*\\{[^}]*border:\\s*'border-[^']+'`)
      );
    }
  });
});
