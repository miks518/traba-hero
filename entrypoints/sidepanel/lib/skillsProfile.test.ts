// The manual skills profile, built without any file.
//
// This module owns everything that must be true about a typed profile before
// the match pipeline will accept it: the backend's `ResumeData` caps each list
// at 100 items and each item at 200 characters, and a list over either bound is
// rejected with a 422 — not truncated — because a silently dropped item would
// claim the match covered skills it never saw. The caps are therefore applied
// here, at the only place a typed profile is built.
//
// `industries` is empty on purpose: the questionnaire deliberately does not ask
// about industries, and an empty list renders as absent rather than as a claim
// that the person works in no industry.

import { describe, it, expect } from 'vitest';
import {
  splitList,
  buildSkillsProfile,
  sanitizeManualProfile,
  MANUAL_PROFILE_KEY,
  EXPERIENCE_BANDS,
} from './skillsProfile';

describe('splitList', () => {
  it('splits on commas, newlines and semicolons, and trims each item', () => {
    expect(splitList('MS Excel,\ncash handling; Food prep,  customer service')).toEqual([
      'MS Excel',
      'cash handling',
      'Food prep',
      'customer service',
    ]);
  });

  it('drops empty items so a trailing comma cannot become a blank chip', () => {
    expect(splitList('BPO, ,, ,')).toEqual(['BPO']);
  });

  it('truncates an item to 200 characters, the backend cap for one skill', () => {
    const long = 'x'.repeat(500);
    expect(splitList(long)[0]).toHaveLength(200);
  });

  it('caps the list at 100 items, the backend cap for the skills list', () => {
    const many = Array.from({ length: 150 }, (_, i) => `skill ${i}`).join(', ');
    expect(splitList(many)).toHaveLength(100);
  });
});

describe('buildSkillsProfile', () => {
  it('combines typed skills with the checked soft skills', () => {
    const profile = buildSkillsProfile({
      skillsText: 'Cash handling',
      softSkills: ['Communication', 'Teamwork'],
      experienceText: 'Service crew',
      years: 2,
    });
    expect(profile?.skills).toEqual(['Cash handling', 'Communication', 'Teamwork']);
  });

  it('does not repeat a soft skill the user already typed', () => {
    // Case-insensitive: the checkbox says "Communication", the user typed
    // "communication" — one chip, or the preview asserts the person claimed it
    // twice.
    const profile = buildSkillsProfile({
      skillsText: 'communication',
      softSkills: ['Communication', 'Teamwork'],
      experienceText: '',
      years: 0,
    });
    expect(profile?.skills).toEqual(['communication', 'Teamwork']);
  });

  it('carries the years band, the previous roles, and leaves industries and summary empty', () => {
    const profile = buildSkillsProfile({
      skillsText: 'Excel',
      softSkills: [],
      experienceText: 'Sales assistant, Encoder',
      years: 4,
    });
    expect(profile).toEqual({
      skills: ['Excel'],
      experience_years: 4,
      job_titles: ['Sales assistant', 'Encoder'],
      industries: [],
      summary: '',
      source: 'manual',
    });
  });

  it('returns null when not one skill was given, so an empty profile cannot reach matching', () => {
    const profile = buildSkillsProfile({
      skillsText: '',
      softSkills: [],
      experienceText: 'Service crew',
      years: 0,
    });
    expect(profile).toBeNull();
  });
});

describe('sanitizeManualProfile', () => {
  const valid = {
    skills: ['Excel'],
    experience_years: 2,
    job_titles: ['Encoder'],
    industries: [],
    summary: '',
    source: 'manual',
  };

  it('accepts a stored manual profile', () => {
    expect(sanitizeManualProfile(valid)).toEqual(valid);
  });

  it('rejects anything that is not a manual profile', () => {
    // Only manual profiles are persisted. A stored object without the marker
    // never came from this form, and reading it back would present an
    // extracted resume as a typed one.
    expect(sanitizeManualProfile({ ...valid, source: undefined })).toBeNull();
    expect(sanitizeManualProfile({ skills: 'Excel' })).toBeNull();
    expect(sanitizeManualProfile(null)).toBeNull();
    expect(sanitizeManualProfile('Excel')).toBeNull();
  });

  it('rejects a profile whose list fields are not string lists', () => {
    expect(sanitizeManualProfile({ ...valid, skills: [1, 2] })).toBeNull();
    expect(sanitizeManualProfile({ ...valid, skills: 'Excel' })).toBeNull();
    expect(sanitizeManualProfile({ ...valid, experience_years: 'two' })).toBeNull();
  });
});

describe('EXPERIENCE_BANDS', () => {
  it('offers a band for every experience shape, in the order they are asked', () => {
    expect(EXPERIENCE_BANDS.map((b) => b.id)).toEqual([
      'first',
      'under-1',
      '1-3',
      '3-5',
      '5-plus',
    ]);
  });

  it('maps each band to the number the match prompt reads', () => {
    // The numbers are what `experience_years` carries into matching: a first-
    // time seeker is 0, not a guess, and "less than 1" is half a year rather
    // than being rounded up to something they have not done yet.
    const years = Object.fromEntries(EXPERIENCE_BANDS.map((b) => [b.id, b.years]));
    expect(years).toEqual({ first: 0, 'under-1': 0.5, '1-3': 2, '3-5': 4, '5-plus': 6 });
  });
});

describe('MANUAL_PROFILE_KEY', () => {
  it('is the storage key the panel reads and writes', () => {
    // Named once so the write in the view and the read on load cannot drift
    // into two keys that each look empty.
    expect(MANUAL_PROFILE_KEY).toBe('manualProfile');
  });
});
