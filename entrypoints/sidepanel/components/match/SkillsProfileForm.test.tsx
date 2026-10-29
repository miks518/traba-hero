// The form a reader fills in when they would rather not upload a file.
//
// These tests assert the contract the rest of the system depends on: Save
// produces exactly the `ResumeData` the match pipeline already consumes, with
// `source: 'manual'` marking where it came from, and Save cannot fire on an
// empty profile. The parsing and capping rules live in `lib/skillsProfile` and
// have their own tests; this file covers the wiring between the controls and
// that builder.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import React from 'react';
import { SkillsProfileForm } from './SkillsProfileForm';
import type { ResumeData } from '../../types';

afterEach(cleanup);

function renderForm(onSave = vi.fn()) {
  render(React.createElement(SkillsProfileForm, { onSave }));
  return onSave;
}

function typeSkills(text: string) {
  fireEvent.change(screen.getByLabelText(/your skills/i), { target: { value: text } });
}

describe('SkillsProfileForm', () => {
  it('builds the profile from the typed skills, the ticks, the roles and the band', () => {
    const onSave = renderForm();

    typeSkills('MS Excel, cash handling');
    fireEvent.click(screen.getByRole('checkbox', { name: 'Communication' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Teamwork' }));
    fireEvent.change(screen.getByLabelText(/previous work experience/i), {
      target: { value: 'Service crew' },
    });
    fireEvent.click(screen.getByRole('radio', { name: '3 – 5 years' }));
    fireEvent.click(screen.getByRole('button', { name: /save profile/i }));

    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave).toHaveBeenCalledWith({
      skills: ['MS Excel', 'cash handling', 'Communication', 'Teamwork'],
      experience_years: 4,
      job_titles: ['Service crew'],
      industries: [],
      summary: '',
      source: 'manual',
    } satisfies ResumeData);
  });

  it('saves zero years when the reader never touched the experience band', () => {
    // The audience is entry-level, so "First job" is the default the form
    // assumes — and 0 is the honest number for it, not a guess upward.
    const onSave = renderForm();
    typeSkills('Excel');
    fireEvent.click(screen.getByRole('button', { name: /save profile/i }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ experience_years: 0 }));
  });

  it('keeps Save disabled until at least one skill exists', () => {
    const onSave = renderForm();

    const save = screen.getByRole('button', { name: /save profile/i });
    expect(save).toHaveProperty('disabled', true);
    expect(screen.getByText(/add at least one skill/i)).toBeTruthy();

    fireEvent.click(screen.getByRole('checkbox', { name: 'Teamwork' }));
    expect(save).toHaveProperty('disabled', false);

    fireEvent.click(screen.getByRole('checkbox', { name: 'Teamwork' }));
    expect(save).toHaveProperty('disabled', true);
    expect(onSave).not.toHaveBeenCalled();
  });

  it('does not save a skill twice when the tick list already covers what was typed', () => {
    const onSave = renderForm();
    typeSkills('communication');
    fireEvent.click(screen.getByRole('checkbox', { name: 'Communication' }));
    fireEvent.click(screen.getByRole('button', { name: /save profile/i }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ skills: ['communication'] }));
  });

  it('shows every soft skill as an unticked checkbox', () => {
    renderForm();
    // One assertion per skill the form offers — the list is the questionnaire's
    // scope, and a skill silently missing from it is a question never asked.
    for (const skill of [
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
    ]) {
      expect(screen.getByRole('checkbox', { name: skill })).toHaveProperty('checked', false);
    }
  });
});
