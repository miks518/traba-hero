import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup, fireEvent } from '@testing-library/react';
import React from 'react';
import { FullDetails } from './FullDetails';
import { WhatWeChecked } from './WhatWeChecked';
import type { VerificationItem, VerificationResult } from '../../types';

/**
 * The panel used to drop `VerificationItem.explanation` on the floor.
 *
 * Every check carries the model's own account of what decided its status. It was
 * parsed, bound to a retrieved URL, weighed by `risk_calculator`, serialised onto
 * the wire, typed on the client — and then never rendered. `WhatWeChecked` drew
 * the label alone, so a `red` Channel Match appeared as the two words "Channel
 * Match" in a red bucket with no sentence anywhere on screen explaining what
 * contradicted what. A reader cannot act on a finding they cannot read, and the
 * developer could not evaluate a fix to the verification stage while the panel
 * withheld its output.
 *
 * These tests pin the four things that made that possible, so it cannot come
 * back quietly: the sentences render, the libel filter is shared rather than
 * reimplemented, the disclosure survives when the sentences are the only thing
 * behind it, and it wears the assessment's tone.
 */

afterEach(cleanup);

function item(over: Partial<VerificationItem> = {}): VerificationItem {
  return {
    label: 'Channel Match',
    status: 'contradicted',
    explanation: "The posting directs applicants to recruitment.ched@outlook.com, which is not on the employer's own domain.",
    source_title: 'CHED official website',
    source_url: 'https://ched.gov.ph/',
    ...over,
  };
}

function result(over: Partial<VerificationResult> = {}): VerificationResult {
  return {
    items: [],
    report: '',
    recommendation: '',
    ...over,
  } as VerificationResult;
}

/** A result carrying all three blocks, so every one of them renders. */
const full = result({
  items: [item()],
  report: 'The search returned two results.',
  evidence: [{ title: 'CHED official website', url: 'https://ched.gov.ph/', snippet: 'Regional Office VI' }],
});

/** Open the disclosure and hand back its rendered text. */
function opened(container: HTMLElement): string {
  const toggle = container.querySelector('[data-role="full-details-toggle"]');
  expect(toggle).not.toBeNull();
  fireEvent.click(toggle as Element);
  return container.textContent ?? '';
}

describe('a check carries the sentence that decided it', () => {
  it('renders the explanation the model wrote', () => {
    const { container } = render(
      React.createElement(FullDetails, { result: result({ items: [item()] }) }),
    );
    const text = opened(container);
    expect(text).toContain('recruitment.ched@outlook.com');
    expect(text).toContain('not on the employer');
  });

  it('renders the label too, so the row matches the bucket above it', () => {
    const { container } = render(
      React.createElement(FullDetails, { result: result({ items: [item()] }) }),
    );
    expect(opened(container)).toContain('Channel Match');
  });

  it('links the source the finding was bound to', () => {
    const { container } = render(
      React.createElement(FullDetails, { result: result({ items: [item()] }) }),
    );
    opened(container);
    const link = container.querySelector('a[href="https://ched.gov.ph/"]');
    expect(link).not.toBeNull();
    expect(link?.textContent).toContain('CHED official website');
  });

  it('groups a contradicted check under Contradicted, in the order the summary uses', () => {
    const { container } = render(
      React.createElement(FullDetails, {
        result: result({ items: [item(), item({ label: 'Company Existence', status: 'confirmed' })] }),
      }),
    );
    opened(container);
    const groups = Array.from(container.querySelectorAll('[data-role="check-details"] [data-group]'));
    // `groupBy`'s own order — contradicted, confirmed, supported, unknown — not
    // the order the items happened to arrive in, and not a copy of the summary's.
    // Both components call the same function, so a label above lands on its
    // sentence below.
    expect(groups.map((g) => g.getAttribute('data-group'))).toEqual([
      'contradicted',
      'confirmed',
    ]);
  });

  it('says nothing before the reader opens it', () => {
    const { container } = render(
      React.createElement(FullDetails, { result: result({ items: [item()] }) }),
    );
    expect(container.textContent).not.toContain('recruitment.ched@outlook.com');
  });
});

describe('the disclosure is where model prose becomes visible, so the filter guards it', () => {
  /**
   * `shouldShowCheck` hides an `unknown` Reputation because that finding used to
   * read "The search results do not contain any scam reports, fraud warnings,
   * formal complaints…" — the words *scam* and *fraud* beside a named company,
   * in order to report nothing. That was the panel's only surface for
   * per-check model prose, so the exposure was one label wide. Rendering the
   * sentences makes this the surface where those words would actually appear,
   * so importing the same function is what keeps one policy rather than two.
   */
  it('hides an unsettled Reputation explanation that WhatWeChecked also hides', () => {
    const reputation = item({
      label: 'Reputation',
      status: 'unknown',
      explanation: 'The search results do not contain any scam reports, fraud warnings or complaints.',
      source_title: '',
      source_url: '',
    });

    const details = render(React.createElement(FullDetails, { result: result({ items: [reputation] }) }));
    // Nothing to show and no prose or evidence to show, so the disclosure
    // withdraws entirely — which is the assertion being tested.
    expect(details.container.querySelector('[data-role="full-details"]')).toBeNull();

    const summary = render(React.createElement(WhatWeChecked, { result: result({ items: [reputation] }) }));
    expect(summary.container.textContent).not.toContain('Reputation');
  });

  it('still shows a contradicted Reputation, because it is the finding that carries weight', () => {
    const reputation = item({
      label: 'Reputation',
      status: 'contradicted',
      explanation: 'A result describes a formal complaint filed against this employer.',
      source_title: '',
      source_url: '',
    });
    const { container } = render(
      React.createElement(FullDetails, { result: result({ items: [reputation] }) }),
    );
    expect(opened(container)).toContain('A result describes a formal complaint');
  });

  /**
   * The prompt asks for an *empty* finding on a yellow Reputation. An item that
   * arrives with a label and nothing under it is a placeholder, and an absent
   * thing dressed as a present one is the thing this panel is built not to do.
   */
  it('drops a check whose explanation is blank rather than rendering an empty row', () => {
    const { container } = render(
      React.createElement(FullDetails, {
        result: result({ items: [item({ explanation: '   ' })] }),
      }),
    );
    expect(container.querySelector('[data-role="full-details"]')).toBeNull();
  });
});

describe('the disclosure does not withdraw the evidence', () => {
  /**
   * The regression this guards. The old early return keyed on evidence and
   * report only, so a `red` whose citation `_bind_to_retrieved` stripped — an
   * unbacked red is demoted to yellow with its URL cleared — arrived with no
   * source and no evidence entry, and the disclosure holding the sentence that
   * explains the contradiction would have hidden itself.
   */
  it('stays open when an explanation is the only thing behind it', () => {
    const unbound = item({
      status: 'unknown',
      explanation: 'The results place this employer at a different domain than the one the posting names.',
      source_title: '',
      source_url: '',
    });
    const { container } = render(
      React.createElement(FullDetails, {
        result: result({ items: [unbound], report: '', evidence: [] }),
      }),
    );
    expect(container.querySelector('[data-role="full-details"]')).not.toBeNull();
    expect(opened(container)).toContain('a different domain');
  });

  it('withdraws entirely when there is genuinely nothing behind it', () => {
    const { container } = render(
      React.createElement(FullDetails, { result: result({ items: [], report: '', evidence: [] }) }),
    );
    expect(container.querySelector('[data-role="full-details"]')).toBeNull();
  });

  it('still renders for a result that only has prose', () => {
    const { container } = render(
      React.createElement(FullDetails, { result: result({ report: 'The search returned two results.' }) }),
    );
    expect(opened(container)).toContain('The search returned two results.');
  });
});

describe('every block is a container, so the reader can tell the kinds apart', () => {
  /**
   * The complaint this answers. Opening the disclosure produced three bare runs of
   * text separated only by `gap-4`, so where the check findings stopped and the
   * search report began was not visible. That is the exact distinction the
   * component exists to keep — a *finding* is a model sentence about a check, a
   * *report* is its prose summary, a *source* is what retrieval returned — and an
   * undifferentiated column erases it.
   */
  /**
   * The two leaf blocks are cards. The checks block is not, because it is a
   * container for three containers — see the nesting rule below, which replaced
   * this assertion when the groups became cards of their own.
   */
  it('puts the two leaf blocks in cards', () => {
    const { container } = render(React.createElement(FullDetails, { result: full }));
    opened(container);
    for (const role of ['search-report', 'search-evidence']) {
      const el = container.querySelector(`[data-role="${role}"]`);
      expect(el, role).not.toBeNull();
      expect(el?.className).toContain('tactile-card');
      expect(el?.className).toContain('bg-surface-container-lowest');
    }
  });

  it('still marks the checks block, even though it is a flat container', () => {
    const { container } = render(React.createElement(FullDetails, { result: full }));
    opened(container);
    expect(container.querySelector('[data-role="check-details"]')).not.toBeNull();
  });

  /**
   * Four stacked extrusions — one around the group, three around its children —
   * spends the elevation cue on nothing. The shadow is what tells a reader an
   * element is a distinct surface, and it is only worth anything while it means
   * something.
   */
  it('gives the parent a fill and a border but no shadow of its own', () => {
    const { container } = render(React.createElement(FullDetails, { result: full }));
    opened(container);
    const body = container.querySelector('[data-role="full-details-body"]');
    expect(body?.className).toContain('bg-surface-container-low');
    expect(body?.className).toContain('border');
    expect(body?.className).not.toContain('tactile-card');
  });

  it('nests all three inside that one parent', () => {
    const { container } = render(React.createElement(FullDetails, { result: full }));
    opened(container);
    const body = container.querySelector('[data-role="full-details-body"]');
    for (const role of ['check-details', 'search-report', 'search-evidence']) {
      expect(body?.querySelector(`[data-role="${role}"]`), role).not.toBeNull();
    }
  });

  it('marks where the sources begin, which an unlabelled list did not', () => {
    const { container } = render(React.createElement(FullDetails, { result: full }));
    const text = opened(container);
    expect(text).toContain('Sources');
    expect(text).toContain('What the search found');
    expect(text).toContain('What each check found');
  });

  it('still withholds a block it has nothing for', () => {
    const { container } = render(
      React.createElement(FullDetails, { result: result({ items: [item()], report: '' }) }),
    );
    opened(container);
    expect(container.querySelector('[data-role="check-details"]')).not.toBeNull();
    expect(container.querySelector('[data-role="search-report"]')).toBeNull();
    expect(container.querySelector('[data-role="search-evidence"]')).toBeNull();
  });
});

describe('each check group is a card tinted by its own status', () => {
  /**
   * The three groups are the panel's most important distinction — a contradicted
   * claim is not a failed check, it is the check succeeding — and they were three
   * runs of text differing only by a two-word heading. The tint makes the
   * difference a thing you see before you read: a red card is a contradiction
   * before its sentence is a sentence.
   */
  const all = result({
    items: [
      item({ label: 'Company Existence', status: 'confirmed', explanation: 'A result shows the business trading.' }),
      item(),
      item({
        label: 'Official Registration',
        status: 'unknown',
        explanation: 'The results do not mention a registration for this employer.',
        source_title: '',
        source_url: '',
      }),
    ],
  });

  const TINT: Record<string, string> = {
    confirmed: 'status-card-verified',
    contradicted: 'status-card-critical',
    unknown: 'status-card-caution',
  };

  it.each(Object.entries(TINT))('tints the %s group %s', (key, cls) => {
    const { container } = render(React.createElement(FullDetails, { result: all }));
    opened(container);
    const group = container.querySelector(`[data-role="check-details"] [data-group="${key}"]`);
    expect(group, key).not.toBeNull();
    expect(group?.className).toContain(cls);
    expect(group?.className).toContain('tactile-card');
  });

  it('gives could-not-verify the amber tint, since that is what the reader asked for', () => {
    const { container } = render(React.createElement(FullDetails, { result: all }));
    opened(container);
    const group = container.querySelector('[data-role="check-details"] [data-group="unknown"]');
    expect(group?.className).toContain('status-card-caution');
    expect(group?.className).not.toContain('status-card-critical');
  });

  /**
   * A chip-coloured chip on a chip-coloured card is invisible, and the failure
   * looks like the status tint simply not working. The chip keeps its saturated
   * text and only the fill is replaced, so it reads as a label cut out of the card.
   */
  it('cuts the chip out of the card, so it does not vanish into the tint', () => {
    const { container } = render(React.createElement(FullDetails, { result: all }));
    opened(container);
    const chip = container.querySelector('[data-role="check-details"] [data-group="unknown"] span');
    expect(chip?.className).toContain('chip-cutout');
    // Still the status chip underneath, so the label keeps its saturated text.
    expect(chip?.className).toContain('chip-caution');
  });

  it('withholds a group it has no checks for rather than drawing an empty tint', () => {
    const { container } = render(
      React.createElement(FullDetails, { result: result({ items: [item()] }) }),
    );
    opened(container);
    const groups = container.querySelectorAll('[data-role="check-details"] [data-group]');
    expect(groups).toHaveLength(1);
    expect(groups[0].getAttribute('data-group')).toBe('contradicted');
  });

  /**
   * The same rule twice now, and it is stated as a rule rather than fixed twice:
   * a container that holds containers is not itself a card. The wrapper around the
   * three tinted groups must not gain a shadow, or the panel grows a
   * `tactile-card` inside a `tactile-card` again.
   */
  it('leaves the wrapper flat, so no tactile-card nests inside another', () => {
    const { container } = render(React.createElement(FullDetails, { result: full }));
    opened(container);
    const wrapper = container.querySelector('[data-role="check-details"]');
    expect(wrapper?.className).toContain('bg-surface-container-low');
    expect(wrapper?.className).not.toContain('tactile-card');
    // And the leaf block beside it keeps its own.
    expect(container.querySelector('[data-role="search-evidence"]')?.className).toContain('tactile-card');
    // As does the body above both.
    expect(container.querySelector('[data-role="full-details-body"]')?.className).not.toContain('tactile-card');
  });
});

describe('the disclosure wears the assessment tone', () => {
  it.each([
    ['critical', 'tactile-assessment-critical'],
    ['caution', 'tactile-assessment-caution'],
    ['verified', 'tactile-assessment-verified'],
    ['unknown', 'tactile-assessment-unknown'],
  ] as const)('takes %s as %s', (tone, cls) => {
    const { container } = render(
      React.createElement(FullDetails, { result: result({ report: 'x' }), tone }),
    );
    const toggle = container.querySelector('[data-role="full-details-toggle"]');
    expect(toggle?.className).toContain(cls);
    // The surface itself, so the fill is the banner's and not a near-match.
    expect(toggle?.className).toContain('tactile-disclosure');
  });

  it('falls back to unknown rather than to a tone of its own', () => {
    const { container } = render(
      React.createElement(FullDetails, { result: result({ report: 'x' }) }),
    );
    expect(container.querySelector('[data-role="full-details-toggle"]')?.className).toContain(
      'tactile-assessment-unknown',
    );
  });
});