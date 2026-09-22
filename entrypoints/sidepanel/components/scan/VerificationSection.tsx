import React from 'react';
import { Icon } from '../common';
import { VerificationCard } from './VerificationCard';
import type { VerificationResult } from '../../types';

interface VerificationSectionProps {
  result?: VerificationResult;
  loading?: boolean;
  error?: boolean;
  currentQuery?: string;
  noCompanyName?: boolean;
}

export function VerificationSection({ result, loading, error, currentQuery, noCompanyName }: VerificationSectionProps) {
  const hasItems = result && result.items.length > 0;

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

      {noCompanyName && (
        <div className="flex flex-col gap-2 p-3 rounded-lg bg-error/10 border border-error/30">
          <div className="flex items-center gap-2">
            <Icon name="shield_person" className="text-error" />
            <span className="font-label-md font-bold text-error">Unable to Verify</span>
          </div>
          <p className="text-body-sm text-on-surface-variant leading-relaxed">
            The company/business name was not identified in this job posting. Without a verifiable company name, external verification could not be performed.
          </p>
          <span className="text-label-sm font-bold text-error">
            ⚠ Treat this as a high-risk posting — missing company name is a common scam indicator.
          </span>
        </div>
      )}

      {loading && !hasItems && (
        <div className="flex flex-col items-center gap-3 py-4">
          <div className="w-10 h-10 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
          <div className="flex flex-col items-center gap-1 text-center">
            <span className="text-body-sm text-on-surface-variant">Searching the web…</span>
            {currentQuery && (
              <span className="text-label-sm text-on-surface-variant/70 max-w-[250px] truncate">
                {currentQuery}
              </span>
            )}
          </div>
        </div>
      )}

      {hasItems && (
        <div className="flex flex-col gap-2">
          {result!.items.map((item, i) => (
            <VerificationCard key={i} item={item} />
          ))}
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

      {result?.recommendation && (
        <div className="rounded-lg bg-secondary-container/10 p-3">
          <h4 className="text-label-md font-bold text-secondary mb-1">Recommendation</h4>
          <p className="text-body-sm text-on-surface leading-relaxed">
            {result.recommendation}
          </p>
        </div>
      )}

      {error && !noCompanyName && (
        <div className="flex items-center gap-2 py-2 text-body-sm text-on-surface-variant">
          <Icon name="info" className="text-secondary" />
          <span>Verification unavailable — scan results are still valid.</span>
        </div>
      )}
    </div>
  );
}
