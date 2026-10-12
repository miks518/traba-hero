/**
 * The ring and the button must mean the same thing.
 *
 * They are two elements on the same card showing the same finding, so a reader
 * who sees an amber ring above a green button has to work out which one is
 * lying. That is why the level colours are tokens in `tailwind.css` rather than
 * `hsl(...)` literals inside `RiskGauge` - two tables of the same numbers is two
 * chances to disagree, and neither would fail anything.
 */

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(here, '../../../../assets/tailwind.css'), 'utf8');
const gauge = readFileSync(resolve(here, 'RiskGauge.tsx'), 'utf8');

const LEVELS = ['low', 'moderate', 'high', 'critical'] as const;

describe('the risk level colours', () => {
  it('are declared as tokens rather than written into the component', () => {
    for (const level of LEVELS) {
      expect(css).toContain(`--color-risk-${level}:`);
    }
  });

  it('are the values the ring used before they became tokens', () => {
    // The exact hsl() the ring was reading, converted. If someone retunes a
    // level this fails and they retune the token instead of the component.
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

  it('are what the ring stroke reads', () => {
    for (const level of LEVELS) {
      expect(gauge).toContain(`var(--color-risk-${level})`);
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

  it('leave the ring with no literal hsl to drift from', () => {
    // One remaining literal is the out-of-band branch of scoreColor, which is
    // unreachable inside the low band. If someone changes the band maths this
    // is the line that should stop them.
    const literals = gauge.match(/hsl\([^)]*\)/g) ?? [];
    expect(literals.length).toBeLessThanOrEqual(1);
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