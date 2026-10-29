import type { ResumeData } from '../types';

/**
 * The manual skills profile: a `ResumeData` built from what the user typed,
 * with no file and no AI call.
 *
 * It exists so a reader can get into matching without handing over a resume
 * document. Everything here is data the user chose to enter, on their own
 * device, and the only place it meets a model is the match call itself.
 *
 * The shape is the same `ResumeData` the upload path produces, so matching,
 * previewing and clearing work identically for both. `source: 'manual'` is the
 * only difference, and the match request strips it before sending — the
 * backend never asked where a profile came from.
 */

/**
 * The backend's `ResumeData` rejects a list over 100 items with a 422 — it
 * refuses rather than truncates, so a silently dropped skill could never claim
 * a match covered it. The caps are applied here, at the only place a typed
 * profile is built, so saving a profile that matching will refuse is not
 * possible.
 */
export const MAX_PROFILE_ITEMS = 100;

/** The backend's per-item character cap. A longer entry is a paste accident; the head of it is kept. */
export const MAX_PROFILE_ITEM_CHARS = 200;

/** The storage key a saved manual profile lives under. Named once so the write and the read cannot drift apart. */
export const MANUAL_PROFILE_KEY = 'manualProfile';

/**
 * The experience bands, newest reading first.
 *
 * "Less than 1 year" is 0.5 rather than a rounded-up 1: the number travels
 * into the match prompt, and a year the person has not worked is not ours to
 * give them. "First job" is 0 — a fact, not an absence.
 */
export const EXPERIENCE_BANDS = [
  { id: 'first', label: 'First job', years: 0 },
  { id: 'under-1', label: 'Less than 1 year', years: 0.5 },
  { id: '1-3', label: '1 – 3 years', years: 2 },
  { id: '3-5', label: '3 – 5 years', years: 4 },
  { id: '5-plus', label: 'More than 5 years', years: 6 },
] as const;

export type ExperienceBandId = (typeof EXPERIENCE_BANDS)[number]['id'];

/**
 * Split a typed list into items: commas, newlines and semicolons are all
 * separators, because a reader typing ten skills does not think about which
 * one the form wants. Empty items are dropped, each item is trimmed to the
 * backend's per-item cap, and the whole list to the backend's list cap.
 */
export function splitList(input: string): string[] {
  return input
    .split(/[\n,;]+/)
    .map((item) => item.trim().slice(0, MAX_PROFILE_ITEM_CHARS))
    .filter(Boolean)
    .slice(0, MAX_PROFILE_ITEMS);
}

export interface SkillsProfileInput {
  skillsText: string;
  softSkills: string[];
  experienceText: string;
  years: number;
}

/**
 * Build the profile from the form's answers, or `null` when it holds no skill.
 *
 * A profile with no skill cannot match anything, so it is not a profile — the
 * caller keeps the Save button disabled instead. Checked soft skills join the
 * typed ones without repeating them: the same skill under two casings is one
 * claim, and the preview renders one chip per claim.
 */
export function buildSkillsProfile(input: SkillsProfileInput): ResumeData | null {
  const typed = splitList(input.skillsText);
  const seen = new Set(typed.map((skill) => skill.toLowerCase()));
  const soft = input.softSkills.filter((skill) => {
    const key = skill.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const skills = [...typed, ...soft];
  if (skills.length === 0) return null;

  return {
    skills: skills.slice(0, MAX_PROFILE_ITEMS),
    experience_years: input.years,
    job_titles: splitList(input.experienceText),
    // The questionnaire deliberately does not ask about industries. An empty
    // list renders as absent — it never claims the person works in none.
    industries: [],
    summary: '',
    source: 'manual',
  };
}

/**
 * Validate a value read back from storage as a manual profile.
 *
 * Storage returns `unknown`: a written key could hold anything, and a
 * malformed object must not become a render crash or — worse — an extracted
 * resume presented as a typed one. Only a shape-complete object carrying the
 * manual marker passes.
 */
export function sanitizeManualProfile(raw: unknown): ResumeData | null {
  if (!raw || typeof raw !== 'object') return null;
  const data = raw as Record<string, unknown>;
  if (data.source !== 'manual') return null;
  if (typeof data.experience_years !== 'number') return null;
  if (typeof data.summary !== 'string') return null;
  for (const key of ['skills', 'job_titles', 'industries'] as const) {
    if (!Array.isArray(data[key])) return null;
    if (!(data[key] as unknown[]).every((item) => typeof item === 'string')) return null;
  }
  return data as unknown as ResumeData;
}

/** Read the saved manual profile, or `null` when there is none or storage is unavailable. */
export function loadManualProfile(): Promise<ResumeData | null> {
  return new Promise((resolve) => {
    try {
      // @ts-ignore - storage API available in extension context
      chrome.storage.local.get([MANUAL_PROFILE_KEY], (result) => {
        resolve(sanitizeManualProfile(result[MANUAL_PROFILE_KEY]));
      });
    } catch {
      resolve(null);
    }
  });
}

/** Save a manual profile. Only manual profiles are persisted — an extracted resume keeps the panel's session-only behaviour. */
export function saveManualProfile(data: ResumeData): void {
  try {
    // @ts-ignore - storage API available in extension context
    chrome.storage.local.set({ [MANUAL_PROFILE_KEY]: data });
  } catch {}
}

/** Remove a saved manual profile. Called when the reader deletes their profile or replaces it with an upload. */
export function clearManualProfile(): void {
  try {
    // @ts-ignore - storage API available in extension context
    chrome.storage.local.remove(MANUAL_PROFILE_KEY);
  } catch {}
}
