import React from 'react';

export interface JobMetaProps {
  /** When this was scanned. Absent for a live scan until one completes. */
  timestamp?: string;
  /** The role as the posting states it. */
  title?: string;
  /** The employer, when the posting named one. */
  employer?: string | null;
}

function formatScannedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  // Fixed format rather than `toLocaleString`, for two reasons: the panel must
  // not shift its layout with the reader's locale, and a stored history entry
  // re-opened months later should read as the moment it was taken rather than
  // as "0 seconds ago".
  return d
    .toLocaleString('en-GB', {
      weekday: 'short',
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
    .toUpperCase();
}

/**
 * The subject line: when this was scanned, who is hiring, and what the role is.
 *
 * **The employer is the heading, not the role.** The report is a reading of an
 * employer — the establishment is one of the verdict's two axes — so the name
 * the reader is being asked to trust leads, and the role sits beneath it as the
 * thing being offered. The role is frequently a whole sentence lifted from the
 * posting ("Sales associate wanted at Acme Trading in Davao"), which reads as a
 * headline only by accident of length; the employer is the stable subject.
 *
 * **The design's third element is not here.** The HTML reads
 * "Northbridge Talent Solutions · posted 2 days ago on a job board", and both
 * halves of that are unsupportable. The extension screenshots a region of a page
 * and has no idea where the posting came from — job board, Facebook group, or a
 * forwarded chat message — so "posted 2 days ago" is a claim about a fact the
 * system does not hold, and inferring it would be the same move as the retired
 * score: presenting an unmeasured figure as an observation.
 *
 * The employer heading renders only when there is one. A posting that named no
 * employer gets `CompanyNameNeeded` further down, which says so in more detail
 * and with a dashed edge; repeating "no employer" here as well would state the
 * same missing input twice and read as two separate problems. The role line
 * stays, at its smaller size, because the role is still a fact about the scan.
 */
export function JobMeta({ timestamp, title, employer }: JobMetaProps) {
  const scannedAt = timestamp ? formatScannedAt(timestamp) : '';
  const hasEmployer = Boolean(employer && employer.trim().length > 0);

  // Nothing to say at all: no title and no scan time. An empty subject block
  // would be a container asserting that something was scanned.
  if (!scannedAt && !title) return null;

  return (
    <section className="px-1 flex flex-col gap-0.5" data-role="job-meta">
      {scannedAt && (
        <p className="text-label-sm font-semibold tracking-wider text-on-surface-variant uppercase">
          Scanned {scannedAt}
        </p>
      )}
      {hasEmployer && (
        <h1 className="text-headline-sm font-headline font-bold text-on-surface tracking-tight leading-tight">
          {employer!.trim()}
        </h1>
      )}
      {title && (
        <p className="text-body-sm text-on-surface-variant leading-snug">{title}</p>
      )}
    </section>
  );
}

export default JobMeta;
