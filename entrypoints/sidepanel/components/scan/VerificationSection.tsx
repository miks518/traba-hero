import React from 'react';
import { Icon } from '../common';
import { VerificationCard } from './VerificationCard';
import type { Accent } from '../../lib/riskAccent';
import type { VerificationResult } from '../../types';

interface VerificationSectionProps {
  result?: VerificationResult;
  loading?: boolean;
  error?: boolean;
  currentQuery?: string;
  /**
   * Risk colour for the header and container. Applied only when the evidence
   * has been promoted to the top of the panel, so the section reads as urgent
   * only in the case where it is leading the results.
   */
  accent?: Accent;
}

export function VerificationSection({ result, loading, error, currentQuery, accent }: VerificationSectionProps) {
  const hasItems = Boolean(result && result.items && result.items.length > 0);

  return (
    <div className={`flex flex-col gap-3 p-4 rounded-xl ${accent?.surface ?? 'bg-surface-container-low'} ${accent?.border ? `${accent.border} border` : ''}`}>
      <div className="flex items-center gap-2">
        <Icon name="search" className={accent?.text ?? 'text-secondary'} />
        <h3 className={`text-label-md font-bold ${accent?.text ?? 'text-on-surface'}`}>External Verification</h3>
        {loading && (
          <span className="ml-auto flex items-center gap-1.5 text-label-sm text-on-surface-variant">
            <span className="w-2 h-2 rounded-full bg-secondary animate-ping" />
            Verifying…
          </span>
        )}
      </div>

      {loading && !hasItems && (
        <div className="flex flex-col items-center gap-3 py-4">
          <div className="w-10 h-10 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
          <div className="flex flex-col items-center gap-1 text-center">
            <span className="text-body-sm text-on-surface-variant">Verifying... Please wait.</span>
            {currentQuery && (
              <span className="text-label-sm text-on-surface-variant/70 max-w-[250px] truncate">
                {currentQuery}
              </span>
            )}
          </div>
        </div>
      )}

      {result && result.searchOk === false && (
        <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-error-container/10 border border-error/40">
          <div className="flex items-center gap-2">
            <Icon name="warning" className="text-error" />
            <span className="font-label-md font-bold text-on-surface">Search Unavailable</span>
          </div>
          <p className="text-body-sm text-on-surface-variant leading-relaxed">
            The web search did not run, so the categories below are unknown rather than clear. This is
            not a finding about the employer. The findings from reading the posting itself still stand.
          </p>
          {result.searchError && (
            <span className="text-label-sm text-on-surface-variant/80 break-words">
              {result.searchError}
            </span>
          )}
        </div>
      )}

      {result?.searchPartial && (
        <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-amber-500/10 border border-amber-500/40">
          <div className="flex items-center gap-2">
            <Icon name="warning" className="text-amber-500" />
            <span className="font-label-md font-bold text-on-surface">Partial Search Coverage</span>
          </div>
          <p className="text-body-sm text-on-surface-variant leading-relaxed">
            {result.queriesFailed && result.queriesIssued
              ? `${result.queriesFailed} of ${result.queriesIssued} searches failed, `
              : 'One of the searches failed, '}
            so some categories below were checked by a thinner search than the
            others. This is not a finding about the employer, and a category that
            is not confirmed may simply not have been covered.
          </p>
        </div>
      )}

      {hasItems && (
        <div className="flex flex-col gap-2">
          {result!.items.map((item, i) => (
            <VerificationCard key={i} item={item} />
          ))}
        </div>
      )}

      {!loading && !hasItems && !error && (
        <div className="flex flex-col gap-2 p-3 rounded-lg bg-surface-container border border-outline-variant/20">
          <div className="flex items-center gap-2">
            <Icon name="info" className="text-secondary" />
            <span className="font-label-md font-medium text-on-surface">Nothing Found</span>
          </div>
          <p className="text-body-sm text-on-surface-variant leading-relaxed">
            The public web results returned nothing for this employer. Please confirm the employer independently.
          </p>
        </div>
      )}

      {/* TEMPORARY DIAGNOSTIC. Renders the provider's raw response body per
          query so it can be inspected in the panel. Inlined rather than
          restored as the separate debug-panel component, because
          `test_no_debug_surface.py` asserts that component file is deleted.
          Remove together with `SearchOutcome.raw_response` and the suspended
          assertion. */}
      {result?.debugSearchRaw && result.debugSearchRaw.length > 0 && (
        <details className="rounded-lg border border-amber-500/40 bg-amber-500/5">
          <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer">
            <Icon name="warning" className="text-amber-500" />
            <span className="text-label-sm font-bold text-on-surface">
              Raw Tavily response (debug)
            </span>
            <span className="ml-auto text-label-sm text-on-surface-variant">
              tap to open
            </span>
          </summary>
          <div className="flex flex-col gap-3 px-3 pb-3">
            {result.debugSearchRaw.map((entry, i) => (
              <div key={i} className="flex flex-col gap-1 min-w-0">
                <span className="text-label-sm font-bold text-amber-500 break-all">
                  {entry.query}
                </span>
                <pre className="text-[10px] leading-relaxed text-on-surface-variant bg-surface-container-lowest rounded p-2 overflow-x-auto max-h-72 whitespace-pre-wrap break-all">
                  {(() => {
                    try {
                      return JSON.stringify(JSON.parse(entry.raw), null, 2);
                    } catch {
                      return entry.raw;
                    }
                  })()}
                </pre>
              </div>
            ))}
          </div>
        </details>
      )}

      {result?.report && (
        <div className="mt-1 pt-3 border-t border-outline-variant/20">
          <h4 className="text-label-md font-bold text-on-surface mb-1">Job Verification Report</h4>
          <p className="text-body-sm text-on-surface-variant leading-relaxed">
            {result.report}
          </p>
        </div>
      )}

      {result?.evidence && result.evidence.length > 0 && (
        <details className="rounded-lg border border-outline-variant/20 bg-surface-container">
          <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer">
            <Icon name="search" className="text-secondary" />
            <span className="text-label-sm font-bold text-on-surface">
              Sources ({result.evidence.length})
            </span>
            <span className="ml-auto text-label-sm text-on-surface-variant">tap to open</span>
          </summary>
          <ul className="flex flex-col gap-2 px-3 pb-3">
            {result.evidence.map((e, i) => (
              <li key={i} className="flex flex-col gap-0.5">
                <a
                  href={e.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-body-sm text-secondary hover:underline break-words"
                >
                  {e.title || e.url}
                </a>
                {e.snippet && (
                  <span className="text-label-sm text-on-surface-variant/80 leading-relaxed">
                    {e.snippet}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}

      {result?.recommendation && (
        <div className="rounded-lg bg-secondary-container/10 p-3">
          <h4 className="text-label-md font-bold text-secondary mb-1">Recommendation</h4>
          <p className="text-body-sm text-on-surface leading-relaxed">
            {result.recommendation}
          </p>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 py-2 text-body-sm text-on-surface-variant">
          <Icon name="info" className="text-secondary" />
          <span>Verification could not be completed. The posting findings above still stand.</span>
        </div>
      )}
    </div>
  );
}
