import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const CARD = join(process.cwd(), 'entrypoints/sidepanel/components/scan/VerificationCard.tsx');
const TAILWIND = join(process.cwd(), 'assets/tailwind.css');

const card = readFileSync(CARD, 'utf-8');
const tailwind = readFileSync(TAILWIND, 'utf-8');

/** The `yellow:` entry of STATUS_CONFIG, up to the `red:` one. */
const yellowConfig = () => card.slice(card.indexOf('yellow:'), card.indexOf('red:'));

describe('VerificationCard status colours', () => {
  /**
   * Regression: the neutral "Not confirmed" state used `secondary`, which in the
   * dark theme is #4ade80 — byte-identical to green-400. "Not confirmed" and
   * "Found in results" therefore rendered the same green, so the most common
   * outcome looked like a positive finding.
   */
  it('does not use the accent colour for the neutral status', () => {
    const yellowBlock = yellowConfig();
    expect(yellowBlock).not.toMatch(/text-secondary/);
    expect(yellowBlock).not.toMatch(/bg-secondary/);
  });

  it('keeps green and red on their own tokens', () => {
    expect(card).toMatch(/green:[\s\S]*?bg-green-500/);
    expect(card).toMatch(/red:[\s\S]*?bg-error/);
  });

  /**
   * "Not confirmed" used `bg-outline/10`, a 10% grey wash on a surface that is
   * already grey. That is not a weak colour, it is an absent one — and this is
   * the most common outcome the panel produces, since a small employer with a
   * thin online footprint returns `yellow` on most of the three categories. The
   * most frequent card rendered as if it carried no status at all.
   */
  it('paints "not confirmed" amber so the card reads as a status', () => {
    // Asserted on the `bg:` key, not a bare /bg-amber-500/: the block also
    // carries `dot: 'bg-amber-500'`, so a looser match would keep passing with
    // the background reverted to grey — the exact bug this test exists for.
    expect(yellowConfig()).toMatch(/bg:\s*'bg-amber-500\/10'/);
  });

  it('paints the status dot amber to match its card', () => {
    expect(yellowConfig()).toMatch(/dot:\s*'bg-amber-500'/);
  });

  it('tints the status badge to match its card', () => {
    // The badge sits inside the card. A card tinted amber with a grey badge
    // reads as a card that failed to get a colour, not as a neutral outcome.
    expect(card).toMatch(/item\.status === 'yellow' \? 'bg-amber-500[^']*text-amber/);
  });

  it('keeps the yellow distinct from the green a positive finding uses', () => {
    // The traffic light has to survive both themes: amber in the dark theme
    // must not collapse toward the green-400 the positive status paints.
    expect(yellowConfig()).not.toMatch(/green/);
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
