/**
 * The level colours are tokens, and the ink on them is measured.
 *
 * They became tokens so the gauge ring and the buttons could not disagree — two
 * elements on the same card showing the same finding, so a reader who saw an
 * amber ring above a green button would have had to work out which one was
 * lying. That reasoning outlived the ring: the ring is gone with the score it
 * drew, and what these assertions protect now is the token pair itself.
 *
 * Two assertions were deleted rather than left failing. `RiskGauge` no longer
 * exists, so "the ring stroke reads the token" and "the ring has no literal hsl
 * to drift from" have no subject. The token values they guarded are still pinned
 * below, which is the part that outlives the component.
 */

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(here, '../../../../assets/tailwind.css'), 'utf8');

const LEVELS = ['low', 'moderate', 'high', 'critical'] as const;

describe('the risk level colours', () => {
  it('are declared as tokens rather than written into a component', () => {
    for (const level of LEVELS) {
      expect(css).toContain(`--color-risk-${level}:`);
    }
  });

  it('are the values the ring used before they became tokens', () => {
    // The exact hsl() the ring was reading, converted. If someone retunes a
    // level this fails and they retune the token rather than a component.
    const expected: Record<string, string> = {
      low: '#4dc819',
      moderate: '#c89c19',
      high: '#c86219',
      critical: '#c81919',
    };
    for (const level of LEVELS) {
      expect(css).toContain(`--color-risk-${level}: ${expected[level]};`);
    }
  });

  it('are what each button variant is built from', () => {
    for (const level of LEVELS) {
      if (level === 'low') continue; // deliberately the default accent
      expect(css).toMatch(
        new RegExp(`\\.tactile-btn-risk-${level}\\s*\\{[^}]*--tactile-base:\\s*var\\(--color-risk-${level}\\)`)
      );
    }
  });
});

describe('the ink on those fills', () => {
  it('gives critical white and the rest the dark ink', () => {
    // Measured, not assumed: low 7.8:1, moderate 6.7:1, high 4.2:1 and critical
    // 2.9:1 on the ink, but 5.8:1 on white. One foreground across all four would
    // fail somewhere, and a button nobody can read is worse than a neutral one.
    expect(css).toMatch(/\.tactile-btn-risk-critical\s*\{[^}]*color:\s*#ffffff/);
    for (const level of ['low', 'moderate', 'high']) {
      expect(css).toMatch(
        new RegExp(`\\.tactile-btn-risk-${level}\\s*\\{[^}]*color:\\s*var\\(--color-on-risk-ink\\)`)
      );
    }
  });

  it('does not reuse the theme-flipping on-surface token for it', () => {
    // --color-on-surface goes light in the dark theme, which would put light
    // text on a mid-tone fill. That is the bug this token exists to avoid.
    expect(css).toMatch(/--color-on-risk-ink:\s*#151c27/);
    expect(css).not.toMatch(/--color-on-risk-ink:[^;]*var\(--color-on-surface\)/);
  });
});
