import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const panel = readFileSync(
  join(root, 'entrypoints/sidepanel/components/scan/CompanyNameNeeded.tsx'),
  'utf-8',
);
const view = readFileSync(
  join(root, 'entrypoints/sidepanel/views/ScamScanView.tsx'),
  'utf-8',
);
const report = readFileSync(
  join(root, 'entrypoints/sidepanel/components/report/ReportPanel.tsx'),
  'utf-8',
);

/**
 * A missing company name is a missing input, not a finding. If it looked like
 * the result cards, a reader would read it as one more result about the post.
 * The distinction has to be visible: the border is dashed where every result
 * container uses a solid one.
 *
 * Two assertions were deleted with `EvidenceSummary.tsx`, which this file used to
 * read to check the panel carried no "Analysis Only" notice. That component is
 * gone — replaced by `WhatWeChecked` and `FullDetails`, neither of which has a
 * notice to carry. The replacement check reads `ReportPanel.tsx` instead.
 */
describe('CompanyNameNeeded', () => {
  it('is visually distinct from the result containers', () => {
    expect(panel).toMatch(/border-dashed/);
    // The result cards all use this exact solid-border treatment.
    expect(panel).not.toMatch(/border border-outline-variant\/20 rounded-xl p-4/);
  });

  it('states plainly that this is not a warning about the post', () => {
    // A softer claim about the reader, not an unverifiable claim about the
    // Philippines: this is a fact about our own output.
    expect(panel).toMatch(/not a warning/i);
  });

  it('tells the reader what to do next', () => {
    expect(panel).toMatch(/scan it again|pick that part|logo|letterhead/i);
  });

  it('does not claim anything about how common nameless posts are', () => {
    expect(panel).not.toMatch(/common in the philippines/i);
  });

  it('offers no text input', () => {
    // The name would flow straight into the verification prompt, which produces
    // a verdict about a named real company. Guidance only, by decision.
    expect(panel).not.toMatch(/<input|<textarea|type="text"/i);
  });
});

describe('where it renders', () => {
  it('replaces the checks section outright rather than sitting above it', () => {
    // A missing input is not one more result. It takes the place of the checks
    // section so a reader cannot read "nothing was checked" as "nothing was
    // found" — the two are different claims and the panel must not blur them.
    expect(report).toMatch(/needsCompanyName \? \(/);
    expect(report).toMatch(/<CompanyNameNeeded \/>/);
  });

  it('and the view passes the flag rather than deciding it', () => {
    expect(view).toMatch(/needsCompanyName/);
  });
});
