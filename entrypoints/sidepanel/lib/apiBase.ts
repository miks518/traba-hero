/**
 * The backend base URL, resolved at runtime rather than baked into the bundle.
 *
 * `WXT_API_BASE` is a build-time value: once it is compiled into the extension,
 * changing it means rebuilding and re-uploading to the Web Store, and every
 * upload goes through review. A backend host can move (a new deploy, a custom
 * domain, a staging host), and none of that should require a re-review of the
 * extension.
 *
 * So the build-time value is only the *default*. A value stored in browser
 * storage under `backendUrl` overrides it, and is read once at startup and kept
 * in sync for the rest of the session.
 */

const STORAGE_KEY = 'backendUrl';

// Trailing slashes are stripped so a stored `.../` and the path joined to it do
// not produce a `//` and a 404 the deploy is not expecting.
function normalise(url: unknown): string {
  return String(url ?? '').trim().replace(/\/+$/, '');
}

const BUILD_BASE = normalise(import.meta.env.WXT_API_BASE) || 'http://localhost:8010';

let cached = BUILD_BASE;

/** The base URL in force. Synchronous, so every `fetch` call site is unchanged. */
export function getApiBase(): string {
  return cached;
}

/** The build-time default, for a UI to offer a "reset" to. */
export function defaultApiBase(): string {
  return BUILD_BASE;
}

/**
 * Load the override (if any) from storage and subscribe to later changes.
 *
 * Awaited once before the app renders, so the first `pingHealth` already uses
 * the stored value. The listener keeps a long-lived panel in step when the URL
 * is changed from the options page without a reload.
 */
export async function initApiBase(): Promise<string> {
  try {
    const result = await browser.storage.local.get(STORAGE_KEY);
    const stored = normalise(result?.[STORAGE_KEY]);
    if (stored) cached = stored;

    browser.storage.onChanged.addListener((changes, area) => {
      if (area !== 'local' || !changes[STORAGE_KEY]) return;
      const next = normalise(changes[STORAGE_KEY].newValue);
      cached = next || BUILD_BASE;
    });
  } catch {
    // Storage unavailable: keep the build-time default rather than failing to start.
  }
  return cached;
}

/**
 * Persist a new backend URL. Empty input resets to the build-time default.
 * Returns the value actually in force after the write.
 */
export async function setApiBase(url: string): Promise<string> {
  const next = normalise(url) || BUILD_BASE;
  cached = next;
  try {
    await browser.storage.local.set({ [STORAGE_KEY]: next === BUILD_BASE ? '' : next });
  } catch {
    // The in-memory value still changed; a failed write only means it is not remembered.
  }
  return next;
}
