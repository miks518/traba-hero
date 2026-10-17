import React, { useId, useState } from 'react';
import { Icon } from '../common';
import type { VerificationResult } from '../../types';

export interface FullDetailsProps {
  result?: VerificationResult;
}

/**
 * The retrieval half, behind a disclosure — slot 8.
 *
 * Split from `WhatWeChecked` because the two answer different questions and carry
 * **opposite honesty requirements.** `WhatWeChecked` asserts that checks were
 * performed, so a line there that cannot be backed by a real check is a false
 * claim about coverage. This one just shows what retrieval returned, which is
 * safe to show whether or not it amounts to anything. Collapsing them back into
 * one component would mean choosing which of those two rules to obey.
 *
 * **The disclosure's own copy does not promise retrieval times.** The design
 * promises "every finding with its source link and *retrieval time*", and nothing
 * records a retrieval time — search results carry a score and content, not a
 * timestamp. A disclosure that overstates its own contents is worse than no
 * disclosure, so the promise is dropped rather than the field faked.
 */
export function FullDetails({ result }: FullDetailsProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  const evidence = result?.evidence ?? [];
  const hasEvidence = evidence.length > 0;

  // Nothing behind the disclosure, so nothing to disclose. An empty disclosure
  // titled "Full details and sources" over an empty column asserts that detail
  // was withheld, which is a different claim from there being none.
  if (!hasEvidence && !result?.report) return null;

  return (
    <section data-role="full-details" data-disclosure data-open={open ? 'true' : 'false'}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="tactile-accordion-btn w-full px-4 py-3 flex items-center justify-between gap-2 text-left cursor-pointer"
      >
        <span className="text-body-md font-headline font-semibold text-on-surface min-w-0">
          Full details and sources
        </span>
        <Icon name="keyboard_arrow_down" className="disclosure-chevron text-on-surface-variant shrink-0" />
      </button>

      {open && (
        <div id={panelId} className="flex flex-col gap-4 mt-3">
          {result?.report && (
            <div className="flex flex-col gap-1 px-1">
              <h4 className="text-label-md font-bold text-on-surface">What the search found</h4>
              <p className="text-body-sm text-on-surface-variant leading-relaxed">{result.report}</p>
            </div>
          )}

          {hasEvidence && (
            <ul className="flex flex-col gap-2.5">
              {evidence.map((e, i) => (
                <li key={i} className="flex flex-col gap-0.5 min-w-0">
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-body-sm text-secondary hover:underline break-words inline-flex items-start gap-1"
                  >
                    <Icon name="open_in_new" className="text-[11px] mt-1 shrink-0" />
                    <span className="min-w-0">{e.title || e.url}</span>
                  </a>
                  {e.snippet && (
                    <span className="text-label-sm text-on-surface-variant leading-relaxed pl-5">
                      {e.snippet}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

export default FullDetails;
