/**
 * An undefined custom property inside a declaration is not an error.
 *
 * `color: var(--color-on-inverse-surface)` where that name exists in neither
 * theme resolves to nothing, and CSS drops the declaration silently. The
 * provenance button then inherited the page's text colour: white on white in
 * dark mode, black on black in light. Nothing failed, no console warning, and
 * `tsc` is clean - it took someone looking at the rendered panel.
 *
 * So this is checked statically. Every `var(--x)` in the stylesheet must have a
 * matching `--x:` definition somewhere in the same file.
 *
 * The check is deliberately coarse. It cannot tell whether a token is defined in
 * the same scope where it is used, which is a real limitation: a token declared
 * only inside `.dark` and referenced outside it would pass here and still fail at
 * runtime. That is why the inverse pair is written out in both themes.
 */

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(here, '../../assets/tailwind.css'), 'utf8');

/** `--name:` at a declaration site. */
const DECLARED = /^\s*(--[a-z0-9-]+)\s*:/gim;

/** `var(--name)` at a use site, with an optional fallback argument. */
const REFERENCED = /var\(\s*(--[a-z0-9-]+)\s*(?:,|\))/g;

function collect(pattern: RegExp): Set<string> {
  const found = new Set<string>();
  for (const match of css.matchAll(pattern)) found.add(match[1]);
  return found;
}

/**
 * Properties that are legitimately not declared in the stylesheet.
 *
 * Each entry names where it is set instead, so the list cannot grow silently.
 * An empty allowlist would make this test fail on a correct stylesheet; an
 * unexplained one would make it pass on a broken one.
 *
 * **Currently empty.** It held `--ring-glow-color`, set per-element by the risk
 * gauge's ring, which was deleted with the score it drew. Nothing sets that
 * property at runtime any more, so the entry was pointing at a file that no
 * longer existed — a stale pointer that would have let a genuine typo through if
 * someone reintroduced the name.
 */
const SET_AT_RUNTIME: Record<string, string> = {};

describe('the stylesheet', () => {
  const declared = collect(DECLARED);
  const referenced = collect(REFERENCED);

  it('references custom properties at all', () => {
    // A guard against the collector silently returning nothing, which would make
    // every assertion below pass vacuously. The file declares 51 and uses 13:
    // most of the palette reaches components as Tailwind utilities like
    // `text-on-surface`, so a `var()` reference is the exception, not the norm.
    expect(declared.size).toBeGreaterThan(40);
    expect(referenced.size).toBeGreaterThan(10);
  });

  it('only references custom properties it defines or sets at runtime', () => {
    const missing = [...referenced]
      .filter((name) => !declared.has(name) && !(name in SET_AT_RUNTIME))
      .sort();

    expect(missing).toEqual([]);
  });

  it('defines the inverse pair under the same name in both themes', () => {
    // The specific pair that broke. Same name, both scopes, so a use site can
    // resolve in either theme.
    expect(css).toMatch(/--color-inverse-on-surface\s*:/);
    expect(declared.has('--color-inverse-on-surface')).toBe(true);
    expect(declared.has('--color-on-inverse-surface')).toBe(false);
  });
});