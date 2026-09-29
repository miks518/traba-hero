// The tactile button must be recolourable, not replaced.
//
// `ScanActions` used to swap the whole class string when a high or critical
// result was on screen, so the button went from a 3D extruded accent key to a flat
// error wash. The colour is supposed to carry the risk; the shape is supposed to
// stay the same control the reader has been pressing all along. A primary action
// that changes its affordance at the same moment it changes its message is
// harder to trust and harder to aim at.
//
// So the 3D is built from one variable and the accent only moves that variable.
// The gradient, the 6px extrusion, the top highlight, and the press animation are
// then byte-identical in both states by construction rather than by careful
// class bookkeeping.
//
// These assert on the stylesheet's structure, because the structure is the fix: a
// test that only checked the class list would pass while the shadow stayed accent.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, it, expect } from 'vitest';

const css = readFileSync(join(process.cwd(), 'assets/tailwind.css'), 'utf-8');

/** The body of one top-level rule, braces included. */
const rule = (selector: string): string => {
  const start = css.indexOf(`${selector} {`);
  expect(start, `${selector} is missing from tailwind.css`).toBeGreaterThan(-1);
  const end = css.indexOf('}', start);
  return css.slice(start, end);
};

describe('the tactile button derives its whole treatment from one colour', () => {
  const accentRule = rule('.tactile-btn-accent');

  it('declares the base colour as a variable', () => {
    // The default is the accent colour. The point is that it is a *variable*,
    // so a modifier can move it without this rule changing.
    expect(accentRule).toMatch(/--tactile-base:\s*var\(--color-secondary\)/);
  });

  it('builds the gradient from that variable, not from secondary directly', () => {
    const gradient = accentRule.slice(accentRule.indexOf('linear-gradient'));
    expect(gradient).toMatch(/var\(--tactile-base\)/);
    // A direct reference here would be a second source of truth: the accent
    // would change the fill and leave the highlight and shadow behind.
    expect(gradient).not.toMatch(/var\(--color-secondary\)/);
  });

  it('builds the extrusion and the top highlight from it too', () => {
    const shadow = accentRule.slice(accentRule.indexOf('box-shadow'));
    expect(shadow).toMatch(/var\(--tactile-base\)/);
    expect(shadow).not.toMatch(/var\(--color-secondary\)/);
  });

  it('keeps the press animation, since the affordance must not change', () => {
    // Dropping the :active press is the same defect as dropping the extrusion:
    // the button stops reading as something you push.
    expect(css).toMatch(/\.tactile-btn-accent:active\s*\{/);
  });
});

describe('there is an error-coloured variant of the same button', () => {
  it('moves the base colour and nothing else', () => {
    const variant = rule('.tactile-btn-error');

    expect(variant).toMatch(/--tactile-base:\s*var\(--color-error\)/);
    // If this rule ever grows a background, a box-shadow, or a border of its
    // own, the two states have diverged again and this is no longer a recolour.
    expect(variant).not.toMatch(/background:/);
    expect(variant).not.toMatch(/box-shadow:/);
    expect(variant).not.toMatch(/border:/);
  });

  it('is a modifier on the tactile class, not a replacement for it', () => {
    // Modelled as a compound so it must be applied *alongside* the base class.
    // A standalone class would let the two be swapped, which is the bug.
    expect(css).toMatch(/\.tactile-btn-accent\.tactile-btn-error/);
  });

  it('uses a design token, never a literal colour', () => {
    const variant = rule('.tactile-btn-error');
    expect(variant).not.toMatch(/#[0-9a-f]{3,6}/i);
    expect(variant).not.toMatch(/hsl\(/);
  });
});
