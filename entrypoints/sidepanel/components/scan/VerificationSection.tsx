import React from 'react';
import { Icon } from '../common';
import { VerificationCard } from './VerificationCard';
import { SearchRawPanel } from './SearchRawPanel';
import type { VerificationResult } from '../../types';

interface VerificationSectionProps {
  result?: VerificationResult;
  loading?: boolean;
  error?: boolean;
  currentQuery?: string;
  noCompanyName?: boolean;
}

export function VerificationSection({ result, loading, error, currentQuery, noCompanyName }: VerificationSectionProps) {
  const hasItems = Boolean(result && result.items && result.items.length > 0);
  const showNoCompany = Boolean(noCompanyName || result?.noCompanyName);

  return (
    <div className="flex flex-col gap-3 p-4 rounded-xl bg-surface-container-low">
      <div className="flex items-center gap-2">
        <Icon name="search" className="text-secondary" />
        <h3 className="text-label-md font-bold text-on-surface">External Verification</h3>
        {loading && (
          <span className="ml-auto flex items-center gap-1.5 text-label-sm text-on-surface-variant">
            <span className="w-2 h-2 rounded-full bg-secondary animate-ping" />
            Verifying…
          </span>
        )}
      </div>

      {showNoCompany && (
        <div className="flex flex-col gap-2 p-3 rounded-lg bg-surface-container border border-outline-variant/20">
          <div className="flex items-center gap-2">
            <Icon name="info" className="text-secondary" />
            <span className="font-label-md font-bold text-on-surface">Analysis Only</span>
          </div>
          <p className="text-body-sm text-on-surface-variant leading-relaxed">
            This posting does not name an employer, so there is nothing to look up online. The findings
            above come only from reading the posting itself, and no risk score was calculated.
          </p>
          <span className="flex items-start gap-1.5 text-label-sm text-on-surface-variant">
            <Icon name="touch_app" className="text-secondary text-base shrink-0" />
            If the employer's name appears elsewhere on the page, pick that part of the posting and scan
            again to enable external verification.
          </span>
        </div>
      )}

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

      {hasItems && (
        <div className="flex flex-col gap-2">
          {result!.items.map((item, i) => (
            <VerificationCard key={i} item={item} />
          ))}
        </div>
      )}

      {!loading && !hasItems && !error && !showNoCompany && (
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

      {/* TEMPORARY raw search dump; remove with SearchRawPanel. */}
      <SearchRawPanel result={result} />

      {error && !showNoCompany && (
        <div className="flex items-center gap-2 py-2 text-body-sm text-on-surface-variant">
          <Icon name="info" className="text-secondary" />
          <span>Verification could not be completed. The posting findings above still stand.</span>
        </div>
      )}
    </div>
  );
}
