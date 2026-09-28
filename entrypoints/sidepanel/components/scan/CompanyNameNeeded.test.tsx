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
const section = readFileSync(
  join(root, 'entrypoints/sidepanel/components/scan/VerificationSection.tsx'),
  'utf-8',
);

/**
 * A missing company name is a missing input, not a finding. If it looked like
 * the result cards, a reader would read it as one more result about the post.
 * The distinction has to be visible: the border is dashed where every result
 * container uses a solid one.
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

describe('verification section', () => {
  it('no longer carries a no-company-name notice', () => {
    // It duplicated the offer analysis, and the new panel replaces it.
    expect(section).not.toMatch(/Analysis Only/);
  });
});

describe('scan view', () => {
  it('renders the panel instead of the verification section when no name', () => {
    expect(view).toMatch(/CompanyNameNeeded/);
  });
});
