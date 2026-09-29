// A high-severity flag's container carried a near-invisible border.
//
// `SEVERITY_STYLES.border` was defined per severity and applied only to the icon
// circle, so the card that actually held the finding had `border-outline-variant/10`
// regardless of how bad the finding was. The severity was communicated entirely
// by a 32px dot, which is the smallest thing on the card. A reader scanning the
// panel for "which of these is the dangerous one" had nothing to scan.
//
// This asserts on the class list. `happy-dom` performs no flex layout and zeroes
// every `getBoundingClientRect()`, so a pixel claim cannot be checked here — only
// that the border token the severity already carries reaches the container.

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const source = readFileSync(
  join(process.cwd(), 'entrypoints/sidepanel/components/scan/RedFlagCard.tsx'),
  'utf-8'
);

describe('the red flag card is outlined by its severity', () => {
  /** The outermost div's className — the card that holds the finding. */
  const containerClass = (): string => {
    const marker = 'className={`bg-surface-container-low';
    const start = source.indexOf(marker);
    expect(start, 'the card container was not found').toBeGreaterThan(-1);
    return source.slice(start, source.indexOf('}`', start) + 2);
  };

  it('applies the severity border to the container, not only the icon', () => {
    // The container is the outermost div; it must carry ${sev.border}.
    expect(containerClass()).toMatch(/\$\{sev\.border\}/);
  });

  it('no longer leaves the container on a near-invisible neutral border', () => {
    // Scoped to the class list, not the file: a comment explaining what was
    // removed would otherwise match its own description of the old value.
    expect(containerClass()).not.toMatch(/border-outline-variant\/10/);
  });

  it('keeps the severity border on the icon as well', () => {
    // Removing it from the icon would lose the cue on the dot itself.
    const icon = source.slice(
      source.indexOf('${sev.bg} ${sev.text} h-8 w-8'),
      source.indexOf('>', source.indexOf('${sev.bg} ${sev.text} h-8 w-8'))
    );
    expect(icon).toMatch(/\$\{sev\.border\}/);
  });

  it('still carries the 3D treatment that makes this card the original design', () => {
    // The other containers in the panel are flat. This one predates them and
    // keeps the highlight; that difference is intentional, not drift.
    expect(source).toMatch(/tactile-card/);
  });

  it('still has a distinct border token per severity', () => {
    for (const severity of ['high', 'mid', 'low']) {
      expect(source).toMatch(
        new RegExp(`${severity}:\\s*\\{[^}]*border:\\s*'border-[^']+'`)
      );
    }
  });
});
