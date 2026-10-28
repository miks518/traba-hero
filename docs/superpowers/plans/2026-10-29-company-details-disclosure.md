# Company Details Disclosure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsed "Company details" disclosure to the report panel that shows the employer details the posting itself states — name, claimed type, registration, SEC records, location, contact channels — reading from `ScanResult` fields that already reach the client but are rendered nowhere.

**Architecture:** One new self-gating component, `CompanyDetails.tsx`, in `components/report/`, modelled mechanically on `FullDetails.tsx` (collapsed `tactile-disclosure`, body renders only when open, renders nothing when there is nothing to disclose) with rows in the `OfferAnalysisCard` icon+label+value pattern. Wired as the first child of `ReportPanel`'s neutral context group, so it drops below the findings on an elevated result like the rest of that group. Pure frontend: no backend, no mapping, no storage changes — `result.companyName`, `result.attributes`, and `result.secRegistration` are read as they are.

**Tech Stack:** React 19 + TypeScript + Tailwind (semantic tokens), vitest + `@testing-library/react`, WXT extension.

**Spec:** Approved in conversation (2026-10-29) with the human partner; the design of record is this header plus **Global Constraints**. The plan argues from `DESIGN.md` (design system), `docs/decisions/scan-channel-enumeration.md` (attribute/separator contracts), and `docs/decisions/report-panel-redesign.md` (panel slot behaviour).

## Global Constraints

- **Semantic tokens only** — `bg-surface-container-low`, `text-on-surface-variant`, `border-outline-variant/20`, etc. Never raw hex (`DESIGN.md`).
- **The disclosure is a container with one operable control.** The header is a real button carrying the `tactile-disclosure` press (no tone modifier — the posting's stated facts are not assessment-coloured; `assets/tailwind.css` resolves the bare class). The body and rows are containers: no press state, no `tactile-card`.
- **Render gate:** the section renders only when the employer is named (`companyName` non-blank) **and** at least one non-name detail exists. No name → no section (`CompanyNameNeeded` already states that missing input). Name only → no section (the heading already says it). Absent detail → no row; never a "not stated" placeholder (`types/index.ts` attributes contract, `lm_client.py` parser).
- **Values are verbatim posting claims.** Read only `companyName`, `attributes.CLAIMED_TYPE`, `attributes.REGISTERED_AS`, `attributes.LOCATION`, `attributes.CONTACT_METHOD`, `secRegistration`. Never `PAY`, `MEETING_SPOT`, `FEE_*`, `MEETING_PLACE_KIND`, and never `attributes.COMPANY` (the name has one source: `companyName`, the same field the `<h1>` binds to).
- **`CONTACT_METHOD` separator contract:** split on `";"`, then each piece on `"|"` — the read side of `lm_client._ATTRIBUTE_JOIN` (`docs/decisions/scan-channel-enumeration.md`). A piece with no `|` is an untyped channel, shown with label `Contact`, never dropped.
- **`CLAIMED_TYPE` lenient read:** the first `"|"`-separated option is the answer — the model may copy the whole format line (`docs/decisions/scan-channel-enumeration.md`, "What `CLAIMED_TYPE` does").
- **Row order is fixed:** Company, Presents itself as, Registered as, SEC registration (one row per entry), Location, Contact (one row per channel). Labels: `Company`, `Presents itself as` (never "Company type" — it is the posting's claim), `Registered as`, `SEC registration`, `Location`, or the channel type as scanned / `Contact`.
- **Tests are offline** and mock at the `lib/api` boundary; component tests use `React.createElement`/JSX + `@testing-library/react` with `afterEach(cleanup)`, following `FullDetails.test.tsx`.
- Before each commit: `npm test -- --run` and `npm run compile` pass from the repo root. One logical change per commit; never commit a secret; do not push.

## Review Focus

Input classes the design implies, each pinned by a test in its owning task:

1. **A `CONTACT_METHOD` piece with no type prefix** (`"09171234567"`) must surface as an untyped `Contact` row, not vanish — the parser saw it and Channel Match acted on it. Pinned by the untyped-channel tests in Task 1.
2. **A scan restored from history without `attributes`** must render no section and not crash. Pinned by the name-only and SEC-only tests in Task 1.
3. **The model copies the whole `CLAIMED_TYPE` option list** — the row shows the first option, not the list. Pinned by the lenient-read tests in Task 1.
4. **`secRegistration` with several entries** — one row each, no key collisions. Pinned in Task 1.
5. **Long values in the 320–400px sidebar** — value spans carry `break-words`/`min-w-0` so the panel does not overflow. Pinned by the class assertion in Task 1.

---

### Task 1: The `CompanyDetails` component

**Files:**
- Create: `entrypoints/sidepanel/components/report/CompanyDetails.tsx`
- Modify: `entrypoints/sidepanel/components/common/Icon.tsx` (extend the `IconName` union — the file's own comment at lines 63–66 documents registering new names as the established practice)
- Test: `entrypoints/sidepanel/components/report/CompanyDetails.test.tsx`

**Interfaces:**
- Consumes: `ScanResult` from `../../types` (`companyName?: string | null`, `attributes?: Record<string, string>`, `secRegistration?: { company_name: string; sec_no: string; status: string; date_approved: string }[]`); `Icon`/`IconName` from `../common/Icon`.
- Produces (Task 2 relies on these): `export function CompanyDetails({ result }: { result: ScanResult }): JSX.Element | null` — self-gating, safe to mount unconditionally. `export type ContactChannel = { type: string; value: string }`; `export function parseContactMethods(raw?: string): ContactChannel[]`; `export function claimedTypeOption(raw?: string): string` (both exported for direct tests).

- [ ] **Step 1: Write the failing tests**

Create `entrypoints/sidepanel/components/report/CompanyDetails.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup, fireEvent } from '@testing-library/react';
import React from 'react';
import { CompanyDetails, parseContactMethods, claimedTypeOption } from './CompanyDetails';
import type { ScanResult } from '../../types';

/**
 * The scan's ATTRIBUTES block and the SEC lookup reached the client and were
 * stored on ScanResult, but nothing rendered them — the only employer data on
 * screen was the company name heading. These tests pin the disclosure that
 * shows what the posting itself states: it renders only when the employer is
 * named and at least one detail exists, absent details get no row, and the
 * separator/lenient-read contracts from docs/decisions/scan-channel-enumeration.md
 * are honoured on the read side.
 */

afterEach(cleanup);

function result(over: Partial<ScanResult> = {}): ScanResult {
  return {
    assessment: null,
    assessmentLabel: '',
    assessed: false,
    riskDescription: '',
    scanningTarget: '',
    anomalies: [],
    isJobPosting: true,
    companyName: 'CHED Regional Office VI',
    attributes: {
      CLAIMED_TYPE: 'government',
      REGISTERED_AS: 'Commission on Higher Education',
      LOCATION: 'Quezon City, Metro Manila',
      CONTACT_METHOD: 'email | hrmo6@ched.gov.ph; email | recruitment.ched@outlook.com',
    },
    ...over,
  };
}

/** Open the disclosure, asserting it started collapsed. */
function open(container: HTMLElement): string {
  const toggle = container.querySelector('[data-role="company-details-toggle"]');
  expect(toggle).not.toBeNull();
  fireEvent.click(toggle as Element);
  return container.textContent ?? '';
}

describe('the render gate', () => {
  it('renders nothing when the posting named no employer', () => {
    const { container } = render(<CompanyDetails result={result({ companyName: null })} />);
    expect(container.querySelector('[data-role="company-details"]')).toBeNull();
  });

  it('renders nothing when the name is the only detail there is', () => {
    const { container } = render(<CompanyDetails result={result({ attributes: undefined })} />);
    expect(container.querySelector('[data-role="company-details"]')).toBeNull();
  });

  it('renders nothing when every stated detail is blank', () => {
    const { container } = render(
      <CompanyDetails result={result({ attributes: { CLAIMED_TYPE: '  ', LOCATION: '' } })} />,
    );
    expect(container.querySelector('[data-role="company-details"]')).toBeNull();
  });
});

describe('the disclosure', () => {
  it('starts collapsed and opens on the toggle', () => {
    const { container } = render(<CompanyDetails result={result()} />);
    const toggle = container.querySelector('[data-role="company-details-toggle"]') as Element;
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(container.querySelector('[data-role="company-details-body"]')).toBeNull();
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(container.querySelector('[data-role="company-details-body"]')).not.toBeNull();
  });

  it('renders the stated details as rows, name first, framed as posting claims', () => {
    const { container } = render(<CompanyDetails result={result()} />);
    const text = open(container);
    expect(text).toContain('As stated in the posting');
    expect(text).toContain('CHED Regional Office VI');
    expect(text).toContain('government');
    expect(text).toContain('Commission on Higher Education');
    expect(text).toContain('Quezon City, Metro Manila');
    const rows = container.querySelectorAll('[data-role="company-detail-row"]');
    expect(rows.length).toBe(6); // name, claimed type, registered as, location, and one row per channel
    expect(rows[0].textContent).toContain('CHED Regional Office VI');
  });

  it('renders one row per contact channel, split on the separator contract', () => {
    const { container } = render(<CompanyDetails result={result()} />);
    const text = open(container);
    expect(text).toContain('hrmo6@ched.gov.ph');
    expect(text).toContain('recruitment.ched@outlook.com');
    expect(container.querySelectorAll('[data-role="company-detail-row"]').length).toBe(6);
  });

  it('reads CLAIMED_TYPE leniently: the first option is the answer', () => {
    const { container } = render(
      <CompanyDetails
        result={result({
          attributes: {
            CLAIMED_TYPE: 'government | private company | recruitment agency | individual | unclear',
          },
        })}
      />,
    );
    expect(open(container)).toContain('government');
    expect(container.textContent).not.toContain('private company');
  });

  it('labels a channel with no type prefix as Contact, never dropping it', () => {
    const { container } = render(
      <CompanyDetails result={result({ attributes: { CONTACT_METHOD: '09171234567' } })} />,
    );
    open(container);
    const rows = Array.from(container.querySelectorAll('[data-role="company-detail-row"]'));
    const contact = rows.find((r) => r.textContent?.includes('09171234567'));
    expect(contact).toBeDefined();
    expect(contact?.textContent).toContain('Contact');
  });

  it('renders one row per SEC registration when the lookup returned them', () => {
    const { container } = render(
      <CompanyDetails
        result={result({
          attributes: undefined,
          secRegistration: [
            {
              company_name: 'CHED Regional Office VI',
              sec_no: 'CN201234567',
              status: 'Registered',
              date_approved: '2012-08-01',
            },
          ],
        })}
      />,
    );
    const text = open(container);
    expect(text).toContain('CN201234567');
    expect(text).toContain('Registered');
    expect(container.querySelectorAll('[data-role="company-detail-row"]').length).toBe(2); // name + SEC
  });

  it('keeps long values inside the narrow panel', () => {
    const { container } = render(<CompanyDetails result={result()} />);
    open(container);
    const value = Array.from(
      container.querySelectorAll('[data-role="company-detail-row"] span'),
    ).find((s) => s.textContent?.includes('Quezon City'));
    expect(value?.className).toContain('break-words');
  });
});

describe('parseContactMethods', () => {
  it('splits the joined channels the planner reads', () => {
    expect(parseContactMethods('email | a@ched.gov.ph; form | bit.ly/x')).toEqual([
      { type: 'email', value: 'a@ched.gov.ph' },
      { type: 'form', value: 'bit.ly/x' },
    ]);
  });

  it('keeps a channel with no type as an untyped contact', () => {
    expect(parseContactMethods('09171234567')).toEqual([{ type: '', value: '09171234567' }]);
  });

  it('returns nothing for a blank or absent value', () => {
    expect(parseContactMethods(undefined)).toEqual([]);
    expect(parseContactMethods('   ')).toEqual([]);
  });
});

describe('claimedTypeOption', () => {
  it('takes the first option when the model copied the format line', () => {
    expect(claimedTypeOption('government | private company | unclear')).toBe('government');
  });

  it('returns the trimmed value when there is no option list', () => {
    expect(claimedTypeOption('  recruitment agency  ')).toBe('recruitment agency');
  });

  it('returns nothing for a blank or absent value', () => {
    expect(claimedTypeOption(undefined)).toBe('');
    expect(claimedTypeOption('   ')).toBe('');
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- --run CompanyDetails`
Expected: FAIL — cannot resolve `./CompanyDetails`.

- [ ] **Step 3: Register the icon names the rows need**

In `entrypoints/sidepanel/components/common/Icon.tsx`, add to the `IconName` union, with a one-line comment each in the file's existing style: `location_on` (Location row), `call` (phone/messenger-type channels), `link` (form channels), `language` (website channels), `contact_page` (untyped-channel fallback). All other row icons already exist in the union (`business`, `badge`, `description`, `verified`, `alternate_email`).

- [ ] **Step 4: Implement `CompanyDetails.tsx`**

`import React, { useId, useState } from 'react'; import { Icon, type IconName } from '../common/Icon'; import type { ScanResult } from '../../types';`

Helpers, exactly these behaviours (tests pin them):

- `parseContactMethods(raw?: string): ContactChannel[]` — return `[]` for blank/absent; split on `";"`, trim each piece, drop empties; each piece split on `"|"`: one part → `{ type: '', value: piece }`, two or more → `{ type: parts[0].trim(), value: parts.slice(1).join(' | ').trim() }`; drop channels whose `value` is blank.
- `claimedTypeOption(raw?: string): string` — trim; blank → `''`; otherwise the text before the first `"|"`, trimmed.

`const CHANNEL_ICONS: Record<string, IconName> = { email: 'alternate_email', phone: 'call', mobile: 'call', form: 'link', website: 'language' };`

Row type: `interface DetailRow { label: string; value: string; icon: IconName }`.

Build, in this order: `name = result.companyName?.trim() ?? ''`; `claimed = claimedTypeOption(result.attributes?.CLAIMED_TYPE)`; `registeredAs` / `location` = trimmed attribute or `''`; `channels = parseContactMethods(...)`; `sec = result.secRegistration ?? []`. `details: DetailRow[]` gains — in order — `claimed` → `{ label: 'Presents itself as', icon: 'badge' }`; `registeredAs` → `{ label: 'Registered as', icon: 'description' }`; one row per `sec` entry → `{ label: 'SEC registration', value: `SEC No. ${entry.sec_no} · ${entry.status}`, icon: 'verified' }`; `location` → `{ label: 'Location', icon: 'location_on' }`; one row per channel → `{ label: channel.type || 'Contact', value: channel.value, icon: CHANNEL_ICONS[channel.type] ?? 'contact_page' }`.

Gate: `if (!name || details.length === 0) return null;` then `rows = [{ label: 'Company', value: name, icon: 'business' }, ...details]`.

JSX — copy `FullDetails.tsx`'s disclosure mechanics with this component's roles and no tone modifier:

```tsx
<section data-role="company-details" data-disclosure data-open={open ? 'true' : 'false'}>
  <button
    type="button"
    aria-expanded={open}
    aria-controls={panelId}
    onClick={() => setOpen((v) => !v)}
    className="tactile-disclosure w-full px-4 py-3 flex items-center justify-between gap-2 text-left cursor-pointer"
    data-role="company-details-toggle"
  >
    <span className="text-body-md font-headline font-semibold min-w-0">Company details</span>
    <Icon name="keyboard_arrow_down" className="disclosure-chevron shrink-0" />
  </button>
  {open && (
    <div
      id={panelId}
      className="mt-3 bg-surface-container-low border border-outline-variant/20 rounded-lg p-3"
      data-role="company-details-body"
    >
      <p className="text-label-sm text-on-surface-variant leading-relaxed">As stated in the posting.</p>
      <ul className="flex flex-col gap-2.5 mt-2">
        {rows.map((row, i) => (
          <li key={`${row.label}-${i}`} className="flex items-start gap-2 min-w-0" data-role="company-detail-row">
            <Icon name={row.icon} className="text-label-md text-on-surface-variant shrink-0 mt-0.5" aria-hidden />
            <div className="flex flex-col min-w-0">
              <span className="text-label-sm text-on-surface-variant uppercase tracking-wider">{row.label}</span>
              <span className="text-body-sm text-on-surface/90 leading-snug break-words">{row.value}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )}
</section>
```

`export default CompanyDetails;` at the end, matching the directory's convention.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `npm test -- --run CompanyDetails`
Expected: PASS (all tests in the file).

- [ ] **Step 6: Commit**

```bash
git add entrypoints/sidepanel/components/report/CompanyDetails.tsx entrypoints/sidepanel/components/report/CompanyDetails.test.tsx entrypoints/sidepanel/components/common/Icon.tsx
git commit -m "feat: add CompanyDetails disclosure for the posting's stated employer details

The scan's ATTRIBUTES block (CONTACT_METHOD, CLAIMED_TYPE, LOCATION,
REGISTERED_AS) and the SEC lookup reached the client and were stored on
ScanResult, but nothing rendered them — the only employer data on screen
was the company name heading. This shows what the posting itself states,
behind a disclosure matching Full details and sources, only when the
employer is named and at least one detail exists. Absent details get no
row; values are verbatim, framed by 'As stated in the posting.'"
```

### Task 2: Wire it into the report panel context group

**Files:**
- Modify: `entrypoints/sidepanel/components/report/ReportPanel.tsx` (imports ~line 7; context group ~line 204-223)
- Modify: `docs/architecture.md` (report panel table, lines 58-69)
- Test: `entrypoints/sidepanel/components/report/CompanyDetails.test.tsx` (append a wiring block)

**Interfaces:**
- Consumes: `CompanyDetails` from Task 1 (`({ result }: { result: ScanResult })`, self-gating).
- Produces: the panel's context group renders, in order, Company details → What we checked (or CompanyNameNeeded) → Full details and sources.

- [ ] **Step 1: Write the failing wiring tests**

Append to `CompanyDetails.test.tsx`:

```tsx
describe('in the report panel', () => {
  function panel(over: Partial<ScanResult> = {}) {
    const r = result(over);
    return (
      <ReportPanel
        result={r}
        verifying={false}
        verificationError={false}
        currentQuery=""
        needsCompanyName={!r.companyName}
        elevate={false}
      />
    );
  }

  it('renders in the context group, before the checks', () => {
    const { container } = render(panel());
    const context = container.querySelector('[data-group="context"]');
    expect(context?.querySelector('[data-role="company-details-toggle"]')).not.toBeNull();
    const children = Array.from(context?.children ?? []).map((c) => c.getAttribute('data-role'));
    expect(children.indexOf('company-details')).toBeLessThan(children.indexOf('full-details'));
  });

  it('renders nothing when the posting named no employer', () => {
    const { container } = render(panel({ companyName: null }));
    expect(container.querySelector('[data-role="company-details"]')).toBeNull();
  });
});
```

Add `import { ReportPanel } from './ReportPanel';` to the file's imports. (`needsCompanyName` is derived from the merged fixture's name, the same way `ScamScanView` derives it, so the two wiring tests exercise both sides of the panel's no-employer branch.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- --run CompanyDetails`
Expected: FAIL — the first wiring test finds no `[data-role="company-details-toggle"]` inside the context group.

- [ ] **Step 3: Wire `ReportPanel.tsx`**

Add `import { CompanyDetails } from './CompanyDetails';` with the other report imports, and make `CompanyDetails` the **first** child of the context group div (`data-group="context"`), above the `needsCompanyName` ternary — the component's own gate handles the no-name state, and sitting above `WhatWeChecked`/`FullDetails` preserves that pair's adjacency (a label above matches its sentence below). With a doc comment in the file's style noting: this is the posting's stated ground for the checks; it drops below the findings on elevate with the rest of the context group.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test -- --run CompanyDetails`
Expected: PASS.

- [ ] **Step 5: Run the whole offline suite and the type check**

Run: `npm test -- --run` and `npm run compile`
Expected: all pass, no new type errors.

- [ ] **Step 6: Document the component in `docs/architecture.md`**

In the report panel table (lines 58-69), insert one row between `AnomalyCards.tsx` and `WhatWeChecked.tsx`:

```markdown
| `CompanyDetails.tsx` | context | The posting's stated employer details behind a disclosure. **Absent, not empty** — renders only when the employer is named and at least one stated detail exists |
```

- [ ] **Step 7: Commit**

```bash
git add entrypoints/sidepanel/components/report/ReportPanel.tsx entrypoints/sidepanel/components/report/CompanyDetails.test.tsx docs/architecture.md
git commit -m "feat: show Company details in the report panel context group

Mounts the disclosure first in the neutral context group, before
What we checked, so the ground the checks stand on is one click away and
the WhatWeChecked/FullDetails adjacency stays intact. It drops below the
findings on an elevated result with the rest of the context group, and
the architecture's panel table records the new component."
```
