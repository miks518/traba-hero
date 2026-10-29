// The stored consent decision.
//
// The modal is only honest if the record behind it is: a decision that was
// never stored, or one stored under a drifting key, would ask again — annoying
// but safe — or worse, skip asking on the strength of a value that means
// nothing. Only `true` is consent. Anything else is a reader who has not
// agreed yet.

import { describe, it, expect, afterEach, vi } from 'vitest';
import {
  getPrivacyConsent,
  setPrivacyConsent,
  PRIVACY_CONSENT_KEY,
} from './privacyConsent';

afterEach(() => {
  vi.restoreAllMocks();
  delete (globalThis as unknown as { chrome?: unknown }).chrome;
});

function storageWith(stored: Record<string, unknown>) {
  const storage = {
    get: vi.fn((_keys: unknown, cb: (r: Record<string, unknown>) => void) => cb({ ...stored })),
    set: vi.fn(),
    remove: vi.fn(),
  };
  (globalThis as unknown as { chrome: unknown }).chrome = { storage: { local: storage } };
  return storage;
}

describe('PRIVACY_CONSENT_KEY', () => {
  it('is the one key the consent decision lives under', () => {
    expect(PRIVACY_CONSENT_KEY).toBe('hasConsentedPrivacy');
  });
});

describe('getPrivacyConsent', () => {
  it('reads the stored decision as true', async () => {
    storageWith({ hasConsentedPrivacy: true });
    await expect(getPrivacyConsent()).resolves.toBe(true);
  });

  it('reads anything but true as not consented', async () => {
    // `false`, a missing key, or a string someone put there by hand: none of
    // them is a consent, and only the exact stored `true` counts.
    storageWith({ hasConsentedPrivacy: false });
    await expect(getPrivacyConsent()).resolves.toBe(false);

    storageWith({});
    await expect(getPrivacyConsent()).resolves.toBe(false);

    storageWith({ hasConsentedPrivacy: 'yes' });
    await expect(getPrivacyConsent()).resolves.toBe(false);
  });

  it('resolves false, and never throws, when storage is unavailable', async () => {
    // Outside the extension context there is no chrome object. A throw here
    // would crash the panel's mount; a reader whose storage cannot be read
    // has not consented as far as we know, so they are asked.
    await expect(getPrivacyConsent()).resolves.toBe(false);
  });
});

describe('setPrivacyConsent', () => {
  it('writes the decision under the consent key', () => {
    const storage = storageWith({});
    setPrivacyConsent(true);
    expect(storage.set).toHaveBeenCalledWith({ hasConsentedPrivacy: true });

    setPrivacyConsent(false);
    expect(storage.set).toHaveBeenCalledWith({ hasConsentedPrivacy: false });
  });

  it('does not throw when storage is unavailable', () => {
    expect(() => setPrivacyConsent(true)).not.toThrow();
  });
});
