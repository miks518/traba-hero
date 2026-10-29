// The profile card says where it came from.
//
// A card headed "Resume Summary" over a profile nobody uploaded would claim a
// document was read that never was — the header names the source, and each
// source gets its own word.

import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import React from 'react';
import { ResumePreview } from './ResumePreview';
import type { ResumeData } from '../../types';

afterEach(cleanup);

function renderPreview(data: ResumeData) {
  render(React.createElement(ResumePreview, { data }));
}

describe('ResumePreview', () => {
  it('heads an uploaded profile "Resume Summary"', () => {
    renderPreview({
      skills: ['Python'],
      experience_years: 3,
      job_titles: ['Developer'],
      industries: ['Software'],
      summary: '',
    });
    expect(screen.getByText('Resume Summary')).toBeTruthy();
  });

  it('heads a typed profile "Manual Profile"', () => {
    renderPreview({
      skills: ['Excel'],
      experience_years: 0,
      job_titles: [],
      industries: [],
      summary: '',
      source: 'manual',
    });
    expect(screen.getByText('Manual Profile')).toBeTruthy();
    expect(screen.queryByText('Resume Summary')).toBeNull();
  });
});
