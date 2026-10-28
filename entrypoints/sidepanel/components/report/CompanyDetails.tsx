import React, { useId, useState } from 'react';
import { Icon, type IconName } from '../common/Icon';
import type { ScanResult } from '../../types';

export interface CompanyDetailsProps {
  result: ScanResult;
}

/** One contact channel, as the read side of the scan's separator contract sees it. */
export interface ContactChannel {
  type: string;
  value: string;
}

/**
 * The channels behind one `CONTACT_METHOD` attribute.
 *
 * The scan joins repeats with `"; "` and writes each as `<type> | <value>`
 * (`lm_client._ATTRIBUTE_JOIN`); the planner reads them by splitting on `";"`
 * then `"|"`, and this is the same read so the panel shows the channels the
 * system actually acted on — see `docs/decisions/scan-channel-enumeration.md`.
 * A piece with no type prefix stays, untyped: the parser saw it and Channel
 * Match weighed it, so dropping it here would hide a fact the check used.
 */
export function parseContactMethods(raw?: string): ContactChannel[] {
  if (!raw || !raw.trim()) return [];
  return raw
    .split(';')
    .map((piece) => piece.trim())
    .filter((piece) => piece.length > 0)
    .map((piece) => {
      const parts = piece.split('|');
      if (parts.length === 1) return { type: '', value: parts[0].trim() };
      return { type: parts[0].trim(), value: parts.slice(1).join(' | ').trim() };
    })
    .filter((channel) => channel.value.length > 0);
}

/**
 * The `CLAIMED_TYPE` a row shows.
 *
 * The scan stores the line verbatim, and a model that copies the format line
 * produces the whole option list. The documented read is lenient — the first
 * option is the answer — and this applies it for display, matching the
 * planner rather than inventing a second meaning for the field.
 */
export function claimedTypeOption(raw?: string): string {
  const value = raw?.trim() ?? '';
  if (!value) return '';
  return value.split('|')[0].trim();
}

const CHANNEL_ICONS: Record<string, IconName> = {
  email: 'alternate_email',
  phone: 'call',
  mobile: 'call',
  form: 'link',
  website: 'language',
};

interface DetailRow {
  label: string;
  value: string;
  icon: IconName;
}

/**
 * The posting's own stated details about the employer, behind a disclosure —
 * the same mechanics as "Full details and sources", collapsed by default.
 *
 * Everything here comes from the posting's ATTRIBUTES block and the SEC
 * lookup, fields that reached the client and were stored but never rendered.
 * The values are what the posting states, verbatim — they are the ground the
 * verification categories test, not findings, so the body says so in one line
 * and no row carries an assessment colour.
 *
 * **The gate is the absent-not-empty rule, twice over.** No employer named, no
 * section — `CompanyNameNeeded` already states that missing input, and a
 * disclosure repeating the heading's empty state would say it a second way.
 * A name with no detail behind it, no section either — one row repeating the
 * `<h1>` is noise dressed as detail. A detail the posting did not state gets
 * no row at all: an empty placeholder would assert the posting said nothing
 * where it said something, or something where it said nothing.
 */
export function CompanyDetails({ result }: CompanyDetailsProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  const name = result.companyName?.trim() ?? '';
  const attrs = result.attributes;
  const claimed = claimedTypeOption(attrs?.CLAIMED_TYPE);
  const registeredAs = (attrs?.REGISTERED_AS ?? '').trim();
  const location = (attrs?.LOCATION ?? '').trim();
  const channels = parseContactMethods(attrs?.CONTACT_METHOD);
  const sec = result.secRegistration ?? [];

  const details: DetailRow[] = [];
  if (claimed) details.push({ label: 'Presents itself as', value: claimed, icon: 'badge' });
  if (registeredAs) {
    details.push({ label: 'Registered as', value: registeredAs, icon: 'description' });
  }
  for (const entry of sec) {
    details.push({
      label: 'SEC registration',
      value: `SEC No. ${entry.sec_no} · ${entry.status}`,
      icon: 'verified',
    });
  }
  if (location) details.push({ label: 'Location', value: location, icon: 'location_on' });
  for (const channel of channels) {
    details.push({
      label: channel.type || 'Contact',
      value: channel.value,
      icon: CHANNEL_ICONS[channel.type] ?? 'contact_page',
    });
  }

  if (!name || details.length === 0) return null;
  const rows: DetailRow[] = [{ label: 'Company', value: name, icon: 'business' }, ...details];

  return (
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
          <p className="text-label-sm text-on-surface-variant leading-relaxed">
            As stated in the posting.
          </p>
          <ul className="flex flex-col gap-2.5 mt-2">
            {rows.map((row, i) => (
              <li
                key={`${row.label}-${i}`}
                className="flex items-start gap-2 min-w-0"
                data-role="company-detail-row"
              >
                <Icon
                  name={row.icon}
                  className="text-label-md text-on-surface-variant shrink-0 mt-0.5"
                  aria-hidden
                />
                <div className="flex flex-col min-w-0">
                  <span className="text-label-sm text-on-surface-variant uppercase tracking-wider">
                    {row.label}
                  </span>
                  <span className="text-body-sm text-on-surface/90 leading-snug break-words">
                    {row.value}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

export default CompanyDetails;
