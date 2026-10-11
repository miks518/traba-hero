/**
 * The heading names what happened, and only calls something "evidence" when
 * there is some.
 *
 * A section titled "Evidence Summary" over an empty list asserts that evidence
 * was summarised. It was not. The reader must be able to tell three states
 * apart: something was found, the search ran and found nothing, and the search
 * could not run — the last two of which are both "no evidence" and must not be
 * dressed as findings.
 *
 * `happy-dom` performs no flex layout and zeroes every `getBoundingClientRect()`,
 * so these assert rendered text, not position or size.
 */

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { EvidenceSummary } from './EvidenceSummary';

afterEach(() => cleanup());

const base = {
  items: [
    { label: 'Company Existence', status: 'green' as const, explanation: 'Has a site.' },
  ],
  searchOk: true,
  report: '',
  recommendation: '',
};

describe('the heading is derived from state', () => {
  it('calls it Evidence Summary when something was found', () => {
    render(<EvidenceSummary result={base} />);
    expect(screen.getByText('Evidence Summary')).not.toBeNull();
  });

  it('does not call an empty result evidence', () => {
    render(<EvidenceSummary result={{ ...base, items: [] }} />);
    expect(screen.queryByText('Evidence Summary')).toBeNull();
    expect(screen.getByText(/found nothing/i)).not.toBeNull();
  });

  it('says the search could not run, separately from finding nothing', () => {
    // The distinction SearchOutcome.ok exists to preserve. Collapsing them
    // would report a deployment problem as a clean employer.
    render(<EvidenceSummary result={{ ...base, searchOk: false, searchError: 'TAVILY_API_KEY is not configured' }} />);
    expect(screen.getByText(/could not run/i)).not.toBeNull();
    expect(screen.queryByText(/found nothing/i)).toBeNull();
  });

  it('names a partial search rather than implying full coverage', () => {
    render(
      <EvidenceSummary
        result={{ ...base, searchPartial: true, queriesFailed: 1, queriesIssued: 3 }}
      />
    );
    expect(screen.getByText(/1 of 3 searches failed/i)).not.toBeNull();
  });

  /**
   * The heading always exists, which is not what the constant heading it
   * replaced did — but a section that announces itself only when it has good
   * news is missing from the heading outline precisely when the reader most
   * needs to find out what was looked up. Deriving the *text* is what this
   * change is for; deleting the heading is not.
   */
  it('always has a heading, whatever the state', () => {
    const states = [
      base,
      { ...base, items: [] },
      { ...base, items: [], searchOk: false, searchError: 'no key' },
      { ...base, items: [], searchPartial: true, queriesFailed: 1, queriesIssued: 2 },
    ];

    for (const result of states) {
      const { container, unmount } = render(<EvidenceSummary result={result} />);
      expect(container.querySelector('h3')?.textContent?.trim()).toBeTruthy();
      unmount();
    }
  });

  it('names each outcome differently rather than defaulting to evidence', () => {
    // Negative assertions alone would pass for a section that said nothing in
    // every state. What matters is that the four outcomes are distinguishable
    // from each other, not merely from "Evidence Summary".
    const headingFor = (result: typeof base | Record<string, unknown>) => {
      const { container, unmount } = render(<EvidenceSummary result={result as typeof base} />);
      const heading = container.querySelector('h3')?.textContent?.trim();
      unmount();
      return heading;
    };

    expect(headingFor({ ...base, items: [] })).toBe('Searched, found nothing');
    expect(headingFor({ ...base, items: [], searchOk: false, searchError: 'no key' }))
      .toBe('Search could not run');
    expect(headingFor({ ...base, items: [], searchPartial: true, queriesFailed: 1, queriesIssued: 2 }))
      .toBe('Partial search coverage');
    expect(headingFor(base)).toBe('Evidence Summary');
  });

  it('prefers the failure over the items when both arrived', () => {
    // `SearchOutcome.ok` and `.results` are independent, so items can land with
    // `search_ok: false`. Calling that "Evidence Summary" would claim we looked
    // when the lookup is what failed.
    render(<EvidenceSummary result={{ ...base, searchOk: false, searchError: 'timeout' }} />);
    expect(screen.getByRole('heading').textContent).toBe('Search could not run');
  });
});

/**
 * The loud-failure path is not a search failure.
 *
 * `VerificationParseError` is raised when the model's answer cannot be read, the
 * stream emits an `error` event, and `verificationError` reaches this component
 * as `error`. The searches themselves completed fine — in the ordinary case
 * they returned results that were then discarded because nobody could parse the
 * answer about them. Rendering "Search could not be completed" files that under
 * retrieval, which sends the reader looking for a problem with the employer's
 * online footprint that does not exist.
 *
 * It must also not claim the search *succeeded*: a request that never came back
 * at all reaches the same prop, and "searches ran fine" would be as untrue as
 * "searches failed". What is missing in every case is a readable answer, which
 * is a fact about this panel's output rather than about the employer.
 */
describe('an unreadable verification result is not a search failure', () => {
  it('does not blame the search in the heading', () => {
    const { container } = render(<EvidenceSummary error />);
    const heading = container.querySelector('h3')?.textContent?.trim();

    expect(heading).not.toMatch(/search/i);
    expect(heading).toBeTruthy();
  });

  it('does not blame the search in the body', () => {
    // Scoped to this component's own text. The advice block is allowed to use
    // any wording it likes; banning a word across the whole section would push
    // the next editor into a synonym rather than making the claim more precise.
    const { container } = render(<EvidenceSummary error />);
    const body = container.querySelector('[data-state="unreadable-result"]');

    expect(body).toBeTruthy();
    expect(body!.textContent).not.toMatch(/search/i);
  });

  it('does not claim the search succeeded either', () => {
    // The overcorrection. A test that only banned "search failed" would pass
    // for copy saying "your search found nothing", which is the same defect
    // pointed the other way.
    const { container } = render(<EvidenceSummary error />);

    expect(container.textContent ?? '').not.toMatch(/search (found|came back|ran)/i);
    expect(container.textContent ?? '').toMatch(/could not read/i);
  });

  it('says plainly that this is not a finding about the employer', () => {
    render(<EvidenceSummary error />);
    expect(screen.getByText(/not a finding about the employer/i)).not.toBeNull();
  });

  it('tells the reader what does still stand', () => {
    // The score is real and the posting indicators are real. A failure here
    // costs the evidence, not the verdict, and the copy has to say so.
    render(<EvidenceSummary error />);
    expect(screen.getByText(/what the posting itself states still stands/i)).not.toBeNull();
  });

  it('is distinguishable from a search that could not run', () => {
    // Two different subsystems failed. Collapsing them back together is the
    // defect this copy exists to fix, so the two headings are pinned as
    // different strings rather than as a shared negative assertion.
    const errored = render(<EvidenceSummary error />);
    const erroredHeading = errored.container.querySelector('h3')?.textContent?.trim();
    errored.unmount();

    const unreadable = render(
      <EvidenceSummary result={{ ...base, items: [], searchOk: false, searchError: 'no key' }} />
    );
    const unreadableHeading = unreadable.container.querySelector('h3')?.textContent?.trim();
    unreadable.unmount();

    expect(erroredHeading).not.toBe(unreadableHeading);
  });

  it('does not also render the empty-result notice', () => {
    // With no result and no items, the default branch is the empty state. It
    // says the search completed and returned nothing — a third claim, and the
    // least true of the three.
    const { container } = render(<EvidenceSummary error />);

    expect(container.querySelector('[data-state="empty"]')).toBeNull();
  });

  it('prefers the unreadable-answer state over the search-failure state', () => {
    // Both can be true at once: the search failed *and* no answer was readable.
    // The heading must still not name the search, or the two fixes cancel out.
    const { container } = render(
      <EvidenceSummary
        error
        result={{ ...base, items: [], searchOk: false, searchError: 'TAVILY_API_KEY is not configured' }}
      />
    );

    expect(container.querySelector('h3')?.textContent?.trim()).not.toMatch(/search/i);
  });
});

describe('nothing found must not read as a warning', () => {
  it('does not tell the reader to confirm the employer', () => {
    // An absent footprint is ordinary for a small Philippine employer, and
    // `build_queries` records this as the traded cost. Telling the reader to go
    // confirm attaches a warning to a non-event.
    render(<EvidenceSummary result={{ ...base, items: [] }} />);
    expect(screen.queryByText(/confirm the employer independently/i)).toBeNull();
  });

  it('puts no instruction in the empty-result body at all', () => {
    // Scoped to the body rather than the section, and asserted as a concept
    // rather than one banned sentence. The advice block is allowed to tell the
    // reader to confirm something — advice is a different claim from a
    // description of a non-event — so banning the words everywhere would push
    // the next editor into a synonym and past the test.
    const { container } = render(
      <EvidenceSummary
        result={{
          ...base,
          items: [],
          recommendation: 'Confirm the employer independently before sending personal details.',
        }}
      />
    );

    // The advice still renders, so this is not a section that merely lacks the
    // words by having been emptied.
    expect(screen.getByText(/Confirm the employer independently/)).not.toBeNull();

    const body = container.querySelector('[data-state="empty"]');
    expect(body).toBeTruthy();
    expect(body!.textContent).not.toMatch(/confirm|verif|check|look into/i);
  });
});

describe('the three states stay apart', () => {
  it('does not say it found nothing when only some searches ran', () => {
    // `search_partial` means the findings are real but one query failed. Saying
    // "found nothing" as well would claim the opposite about coverage.
    const { container } = render(
      <EvidenceSummary
        result={{ ...base, items: [], searchPartial: true, queriesFailed: 2, queriesIssued: 4 }}
      />
    );

    expect(container.querySelector('[data-state="empty"]')).toBeNull();
    expect(container.querySelector('[data-state="partial"]')).toBeTruthy();
    expect(screen.getByText(/2 of 4 searches failed/i)).not.toBeNull();
  });

  it('does not say it found nothing when the search could not run', () => {
    const { container } = render(
      <EvidenceSummary result={{ ...base, items: [], searchOk: false, searchError: 'timeout' }} />
    );

    expect(container.querySelector('[data-state="empty"]')).toBeNull();
    expect(container.querySelector('[data-state="unreadable"]')).toBeTruthy();
  });

  it('states the reason the search did not run', () => {
    // A missing TAVILY_API_KEY is a broken deployment, and reporting it as
    // "nothing found" is how a broken deployment looks like a clean employer.
    render(
      <EvidenceSummary
        result={{ ...base, items: [], searchOk: false, searchError: 'TAVILY_API_KEY is not configured' }}
      />
    );
    expect(screen.getByText(/TAVILY_API_KEY is not configured/)).not.toBeNull();
  });

  it('says nothing at all while a result has not arrived', () => {
    // Loading is its own state. Rendering "found nothing" before anything came
    // back would report a conclusion the panel has not reached.
    const { container } = render(<EvidenceSummary loading />);
    expect(container.querySelector('[data-state="empty"]')).toBeNull();
    expect(screen.queryByText(/found nothing/i)).toBeNull();
  });
});

describe('anomalies lead the summary', () => {
  it('renders them above the search findings', () => {
    const anomalies = [
      { id: 'a1', title: 'Asks for a fee', description: 'The post asks for money.', icon: 'warning' as const, severity: 'high' as const },
    ];
    const { container } = render(<EvidenceSummary result={base} anomalies={anomalies} />);

    const text = container.textContent ?? '';
    expect(text.indexOf('Asks for a fee')).toBeGreaterThan(-1);
    expect(text.indexOf('Asks for a fee')).toBeLessThan(text.indexOf('Has a site.'));
  });
});
