import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const CARD = join(process.cwd(), 'entrypoints/sidepanel/components/scan/VerificationCard.tsx');
const TAILWIND = join(process.cwd(), 'assets/tailwind.css');

const card = readFileSync(CARD, 'utf-8');
const tailwind = readFileSync(TAILWIND, 'utf-8');

describe('VerificationCard status colours', () => {
  /**
   * Regression: the neutral "Not confirmed" state used `secondary`, which in the
   * dark theme is #4ade80 — byte-identical to green-400. "Not confirmed" and
   * "Found in results" therefore rendered the same green, so the most common
   * outcome looked like a positive finding.
   */
  it('does not use the accent colour for the neutral status', () => {
    const yellowBlock = card.slice(card.indexOf('yellow:'), card.indexOf('red:'));
    expect(yellowBlock).not.toMatch(/text-secondary/);
    expect(yellowBlock).not.toMatch(/bg-secondary/);
  });

  it('keeps green and red on their own tokens', () => {
    expect(card).toMatch(/green:[\s\S]*?bg-green-500/);
    expect(card).toMatch(/red:[\s\S]*?bg-error/);
  });

  it('paints the neutral status with a grey token in both themes', () => {
    // `outline` is the neutral grey in this palette; it exists in both themes.
    expect(tailwind).toMatch(/--color-outline:/);
    expect(card).toMatch(/outline/);
  });
});

describe('theme palette', () => {
  it('does not make the accent green identical to the positive green', () => {
    // Guards the underlying cause: if these are ever equal again, a neutral
    // state styled with the accent becomes indistinguishable from a finding.
    const dark = tailwind.slice(tailwind.indexOf('.dark'));
    const secondary = dark.match(/--color-secondary:\s*([#0-9a-fA-F]{6})/)?.[1];
    expect(secondary).toBeDefined();
    // green-400 #4ade80 is what the card uses for a positive status.
    expect(secondary?.toLowerCase()).not.toBe('#4ade80');
  });
});
