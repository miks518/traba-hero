import React, { useState } from 'react';
import { Icon } from '../common/Icon';
import {
  buildSkillsProfile,
  EXPERIENCE_BANDS,
  type ExperienceBandId,
} from '../../lib/skillsProfile';
import type { ResumeData } from '../../types';

export interface SkillsProfileFormProps {
  onSave: (data: ResumeData) => void;
}

/**
 * The soft skills offered as checkboxes.
 *
 * They are here because they are near-universal claims in entry-level postings
 * — a dishwasher who never saw their own habits as skills still has every one
 * of these. The reader ticks what is true; nothing is inferred. "Willing to be
 * trained" is phrased the way Philippine postings phrase it, because that is
 * the word a reader will recognise themselves in.
 */
const SOFT_SKILLS = [
  'Communication',
  'Teamwork',
  'Customer service',
  'Time management',
  'Adaptability',
  'Problem-solving',
  'Attention to detail',
  'Willing to be trained',
  'Work under pressure',
  'Computer literacy',
];

/**
 * The typed alternative to a resume upload.
 *
 * Four questions, no file, no AI call: what you can do, the common habits you
 * tick, the roles you have held, and how long. Saving builds the same
 * `ResumeData` an upload would have produced and nothing leaves the device —
 * the answers only travel when the reader later presses Match, which is the
 * act of sharing them on purpose.
 */
export function SkillsProfileForm({ onSave }: SkillsProfileFormProps) {
  const [skillsText, setSkillsText] = useState('');
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [experienceText, setExperienceText] = useState('');
  const [band, setBand] = useState<ExperienceBandId>('first');

  const years = EXPERIENCE_BANDS.find((b) => b.id === band)?.years ?? 0;
  const hasSkill = skillsText.trim().length > 0 || checked.size > 0;
  const profile = hasSkill
    ? buildSkillsProfile({
        skillsText,
        softSkills: [...checked],
        experienceText,
        years,
      })
    : null;

  const toggleSoftSkill = (skill: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(skill)) {
        next.delete(skill);
      } else {
        next.add(skill);
      }
      return next;
    });
  };

  return (
    <div className="tactile-card p-4 bg-surface-container border border-outline-variant/30 rounded-xl flex flex-col gap-4">
      <div className="flex flex-col gap-0.5">
        <span className="font-label-md text-on-surface-variant uppercase tracking-wider text-[11px]">
          Your profile, without a file
        </span>
        <span className="text-label-sm text-on-surface-variant/70">
          Answer below and the panel builds your profile. Nothing is sent anywhere
          until you match it against jobs yourself.
        </span>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="skills-profile-skills" className="text-label-md text-on-surface">
          Your skills
        </label>
        <textarea
          id="skills-profile-skills"
          value={skillsText}
          onChange={(e) => setSkillsText(e.target.value)}
          placeholder="e.g. MS Excel, cash handling, food preparation — separate with commas"
          rows={2}
          className="w-full rounded-lg bg-surface-container-lowest border border-outline-variant/30 px-3 py-2 text-body-sm text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:border-secondary/50 resize-none"
        />
      </div>

      <fieldset className="flex flex-col gap-1.5 border-0 p-0 m-0">
        <legend className="text-label-md text-on-surface p-0">
          Soft skills <span className="text-on-surface-variant/60 font-normal">(optional)</span>
        </legend>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 mt-0.5">
          {SOFT_SKILLS.map((skill) => (
            <label
              key={skill}
              className="flex items-center gap-2 text-body-sm text-on-surface cursor-pointer"
            >
              <input
                type="checkbox"
                checked={checked.has(skill)}
                onChange={() => toggleSoftSkill(skill)}
                className="w-4 h-4 rounded accent-secondary shrink-0"
              />
              {skill}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="flex flex-col gap-1">
        <label htmlFor="skills-profile-experience" className="text-label-md text-on-surface">
          Previous work experience{' '}
          <span className="text-on-surface-variant/60 font-normal">(optional)</span>
        </label>
        <input
          id="skills-profile-experience"
          type="text"
          value={experienceText}
          onChange={(e) => setExperienceText(e.target.value)}
          placeholder="e.g. Service crew, Sales assistant — separate with commas"
          className="w-full rounded-lg bg-surface-container-lowest border border-outline-variant/30 px-3 py-2 text-body-sm text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:border-secondary/50"
        />
      </div>

      <fieldset className="flex flex-col gap-1.5 border-0 p-0 m-0">
        <legend className="text-label-md text-on-surface p-0">Years of experience</legend>
        <div className="flex flex-col gap-1.5 mt-0.5">
          {EXPERIENCE_BANDS.map((b) => (
            <label
              key={b.id}
              className="flex items-center gap-2 text-body-sm text-on-surface cursor-pointer"
            >
              <input
                type="radio"
                name="skills-profile-years"
                checked={band === b.id}
                onChange={() => setBand(b.id)}
                className="w-4 h-4 accent-secondary shrink-0"
              />
              {b.label}
            </label>
          ))}
        </div>
      </fieldset>

      {!profile && (
        <p className="text-label-sm text-on-surface-variant/70 flex items-center gap-1">
          <Icon name="info" className="text-xs shrink-0" />
          Add at least one skill — type them above or tick the boxes.
        </p>
      )}

      <button
        type="button"
        disabled={!profile}
        onClick={() => {
          if (profile) onSave(profile);
        }}
        className="tactile-btn-accent w-full py-2.5 rounded-lg font-headline-md text-sm flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed active:translate-y-[1px]"
      >
        <Icon name="handshake" className="text-base" />
        Save profile
      </button>
    </div>
  );
}

export default SkillsProfileForm;
