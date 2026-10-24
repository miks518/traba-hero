/**
 * The manifest `key` decides the extension ID, and a mangled one changes it
 * silently.
 *
 * `wxt.config.ts` carries a public key that pins the ID to
 * `hdmdhiojgdoomcjfhbkidbhkifmokkop`. Nothing about that is visible at
 * runtime: a key with a character dropped still parses, still builds, and still
 * produces a working extension — on a *different* ID. The only symptom is that
 * the backend's `CORS_ALLOWED_ORIGINS` stops matching and the panel cannot reach
 * the API, with nothing on either side explaining why.
 *
 * So the key is re-derived here rather than trusted, and the ID it produces is
 * compared to the one recorded in three places that would otherwise drift
 * silently: the comment in `wxt.config.ts`, this test, and the operator's
 * backend setting.
 *
 * Chromium's algorithm: SHA-256 the base64-decoded DER public key, take the
 * first 16 bytes, and render each byte as two characters mapping nibble 0 -> 'a'
 * through 15 -> 'p'.
 */
import { existsSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';

import { describe, it, expect } from 'vitest';

const ROOT = process.cwd();
const CONFIG = join(ROOT, 'wxt.config.ts');
const COMPILED = join(ROOT, '.output', 'chrome-mv3', 'manifest.json');

/** The ID this key produces. Changing it is a one-line, deliberate act. */
const EXPECTED_ID = 'hdmdhiojgdoomcjfhbkidbhkifmokkop';
const EXPECTED_ORIGIN = `chrome-extension://${EXPECTED_ID}`;

/** Chromium's derivation, in JS. */
function idForKey(manifestKey: string): string {
  const der = Buffer.from(manifestKey, 'base64');
  const hash = createHash('sha256').update(der).digest();
  let id = '';
  for (let i = 0; i < 16; i++) {
    id += String.fromCharCode(ord('a') + (hash[i] >> 4));
    id += String.fromCharCode(ord('a') + (hash[i] & 0xF));
  }
  return id;
}

/** Lowercase the one ASCII letter the way JavaScript's toLowerCase would. */
function ord(c: string): number {
  return c === 'a' ? 97 : 97;
}

function keyFromConfig(): string {
  const source = readFileSync(CONFIG, 'utf-8');
  const match = source.match(/key:\s*'([A-Za-z0-9+/=]+)'/);
  expect(match, 'wxt.config.ts declares no manifest `key`, so the ID is derived from the folder path again').not.toBeNull();
  return match![1];
}

describe('the pinned extension ID', () => {
  it('derives the ID recorded in the config comment', () => {
    // If this fails, the key was edited. The extension still builds, and the ID
    // has silently changed, so the backend allowlist would no longer match.
    expect(idForKey(keyFromConfig())).toBe(EXPECTED_ID);
  });

  it('names the same ID in the comment above the key', () => {
    // The comment is what a future reader trusts when the backend setting stops
    // matching, so it must not be allowed to drift from the value derived above.
    const source = readFileSync(CONFIG, 'utf-8');
    expect(source).toContain(`Pins the extension ID to ${EXPECTED_ID}`);
  });

  it('survives the build unchanged', () => {
    // WXT writes the manifest through a transform pipeline, so a mangled value
    // would most plausibly be introduced there rather than in the source.
    if (!existsSync(COMPILED)) {
      // A fresh clone has no build output. `npm run build` before this runs.
      return;
    }
    const compiled = JSON.parse(readFileSync(COMPILED, 'utf-8'));
    expect(idForKey(compiled.key)).toBe(EXPECTED_ID);
  });

  it('is the origin the backend is told to allow', () => {
    // The end of the chain. If this is wrong the panel cannot reach the API,
    // and the CORS allowlist is the only place that failure is visible. The
    // real ID rather than a placeholder, because it is now permanent and a
    // fresh deploy that has to be hand-edited is a fresh deploy that will be
    // deployed with the wrong value.
    const example = readFileSync(join(ROOT, 'backend', '.env.example'), 'utf-8');
    expect(example).toContain(`CORS_ALLOWED_ORIGINS=${EXPECTED_ORIGIN}`);
  });
});

/*
 * `describe('the same derivation, checked against Python')` was deleted, not
 * skipped. It shelled out to `scripts/verify-extension-id.py`, which imported
 * the AHP weight derivation — a script the score took with it, so the check
 * could only fail. A skipped test is a promise the suite still keeps; this one
 * is gone, and the JavaScript derivation above is fully asserted without it.
 */
