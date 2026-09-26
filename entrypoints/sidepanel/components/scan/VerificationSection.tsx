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
            <span className="font-label-md font-bold text-on-surface">Verification Skipped</span>
          </div>
          <p className="text-body-sm text-on-surface-variant leading-relaxed">
            This posting does not name an employer, so there was nothing to look up. The posting itself was still assessed.
          </p>
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

      {result?.recommendation && (
        <div className="rounded-lg bg-secondary-container/10 p-3">
          <h4 className="text-label-md font-bold text-secondary mb-1">Recommendation</h4>
          <p className="text-body-sm text-on-surface leading-relaxed">
            {result.recommendation}
          </p>
        </div>
      )}

      {error && !showNoCompany && (
        <div className="flex items-center gap-2 py-2 text-body-sm text-on-surface-variant">
          <Icon name="info" className="text-secondary" />
          <span>Verification could not be completed. The posting findings above still stand.</span>
        </div>
      )}
    </div>
  );
}
