import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup, fireEvent } from '@testing-library/react';
import React from 'react';
import { CompanyDetails, parseContactMethods, claimedTypeOption } from './CompanyDetails';
import { ReportPanel } from './ReportPanel';
import type { ScanResult, VerificationResult } from '../../types';

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

describe('in the report panel', () => {
  function panel(over: Partial<ScanResult> = {}) {
    const r = result({
      // FullDetails gates itself off without anything to disclose, so an empty
      // verification result would leave the context group with no `full-details`
      // child and the ordering assertion below would compare against -1. A
      // report is the cheapest thing that makes both siblings render.
      verificationResult: { items: [], report: 'The search returned two results.', recommendation: '' } as VerificationResult,
      ...over,
    });
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
