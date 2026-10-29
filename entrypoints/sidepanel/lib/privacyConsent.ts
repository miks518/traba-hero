/**
 * The stored consent decision for processing a resume file.
 *
 * CRITICAL.md Task 2.1. The notice is shown before the first upload; the
 * decision is recorded so the reader answers it once, not on every visit.
 *
 * Only a stored `true` is consent. A missing key, a `false`, or anything a
 * hand-edit left there reads as "not asked yet", which is the safe direction:
 * the worst case is one extra notice, never a skipped one. Storage being
 * unavailable resolves the same way — the panel has no basis to believe
 * agreement happened, so it asks.
 */

export const PRIVACY_CONSENT_KEY = 'hasConsentedPrivacy';

/** Read the stored decision. `false` means the notice has not been accepted. */
export function getPrivacyConsent(): Promise<boolean> {
  return new Promise((resolve) => {
    try {
      // @ts-ignore - storage API available in extension context
      chrome.storage.local.get([PRIVACY_CONSENT_KEY], (result) => {
        resolve(result[PRIVACY_CONSENT_KEY] === true);
      });
    } catch {
      resolve(false);
    }
  });
}

/** Record the decision — the reader agreed, or declined and should be asked again next time. */
export function setPrivacyConsent(consented: boolean): void {
  try {
    // @ts-ignore - storage API available in extension context
    chrome.storage.local.set({ [PRIVACY_CONSENT_KEY]: consented });
  } catch {}
}
