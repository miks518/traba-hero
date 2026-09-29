// Every `border-<custom-token>/<opacity>` class a component uses must be declared.
//
// Tailwind v4 generates an opacity variant for a colour it knows as a literal:
// `.border-amber-500\/40` is built for you. The design system's own tokens are
// different — `error`, `secondary`, `outline` and the surface ramp are declared
// in a plain `:root` block, so Tailwind emits the base `.border-error` and then
// stops. Any opacity variant for those has to be hand-declared in the
// `@layer components` block of `assets/tailwind.css`, and several are.
//
// A class that is not generated does not fail. It does nothing, and the element
// falls back to Tailwind's preflight `border: 0 solid #e5e7eb` — a near-white
// grey. That is exactly what happened to the red flag card: it was given
// `border-error/40`, which was never declared, so a high-severity finding was
// outlined in off-white while its 32px icon, on the declared `/30`, showed red.
// The reader saw a white card and reported "the border is not red".
//
// Only the custom tokens are checked. Testing the default palette colours would
// flag classes that Tailwind generates on its own, which are fine.

import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(process.cwd(), 'entrypoints/sidepanel');
// The stylesheet escapes slashes in class selectors (`.border-error\/30`).
// Dropping them makes the two forms comparable without a fragile regex.
const css = readFileSync(join(process.cwd(), 'assets/tailwind.css'), 'utf-8').replace(/\\/g, '');

/** Tailwind's built-in palette. A `-500` in the name means a literal colour. */
const isDefaultPalette = (variant: string) => /-\d{2,3}\b/.test(variant);

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    if (!/\.tsx?$/.test(entry)) return [];
    if (/\.test\.tsx?$/.test(entry)) return [];
    return [full];
  });
}

function customVariantsUsed(): Array<{ file: string; variant: string }> {
  const found: Array<{ file: string; variant: string }> = [];
  for (const file of sourceFiles(ROOT)) {
    const source = readFileSync(file, 'utf-8');
    // The variant prefix is part of the class: `hover:border-secondary/50` is a
    // different selector from `border-secondary/50`, so it needs its own
    // declaration and matching on the substring alone would pass vacuously.
    for (const match of source.matchAll(/(?:hover:|focus:|active:)?\bborder-[a-z][a-z-]*\/[0-9]{1,3}\b/g)) {
      if (isDefaultPalette(match[0])) continue;
      found.push({ file: file.replace(ROOT, ''), variant: match[0] });
    }
  }
  return found;
}

describe('translucent border classes resolve to something real', () => {
  it('finds the variants to check, so an empty list cannot pass silently', () => {
    // If this returns nothing the check below is vacuous — the exact failure
    // mode this file exists to catch.
    expect(customVariantsUsed().length).toBeGreaterThan(2);
  });

  it('declares every custom-token variant the components use', () => {
    const missing = customVariantsUsed().filter((v) => !css.includes(`.${v.variant}`));

    expect(
      missing,
      `used in components but not declared in @layer components, so they generate ` +
        `nothing and the border falls back to preflight grey (#e5e7eb): ` +
        [...new Set(missing.map((m) => `${m.variant} (${m.file})`))].join(', ')
    ).toEqual([]);
  });
});
