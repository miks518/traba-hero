import React from 'react';
import { Icon } from '../common/Icon';
import type { ScannedJob, JobMatchItem } from '../../types';

export interface JobMatchListProps {
  jobs: ScannedJob[];
  matches: JobMatchItem[];
}

export function JobMatchList({ jobs, matches }: JobMatchListProps) {
  const sorted = [...matches].sort((a, b) => b.score - a.score);

  return (
    <div className="flex flex-col gap-3">
      <span className="font-label-md text-on-surface-variant uppercase tracking-wider text-[11px]">
        Job Matches ({matches.length})
      </span>
      {sorted.map((m) => {
        const job = jobs.find((j) => j.id === m.jobId);
        return (
          <div
            key={m.jobId}
            className="tactile-card p-4 bg-surface-container-low border border-outline-variant/30 rounded-xl flex flex-col gap-3"
          >
            <div className="flex items-center justify-between">
              <span className="font-body-md text-on-surface truncate flex-1">
                {job?.title || 'Scanned Job'}
              </span>
              <div className="flex items-center gap-2 ml-2">
                <span className="text-headline-xs font-headline font-bold text-gold-gradient">
                  {m.score}%
                </span>
                <span className="text-label-sm text-on-surface-variant">
                  {m.label}
                </span>
              </div>
            </div>

            <div className="flex h-1.5 w-full bg-surface-variant rounded-full overflow-hidden shadow-inner">
              <div
                className="h-full bg-secondary rounded-full transition-all"
                style={{ width: `${m.score}%` }}
              />
            </div>

            <div className="flex flex-wrap gap-4 text-body-sm">
              {m.matchedSkills.length > 0 && (
                <div className="flex flex-col gap-1">
                  <span className="text-label-sm text-on-surface-variant">Matched</span>
                  <div className="flex flex-wrap gap-1">
                    {m.matchedSkills.map((s, i) => (
                      <span key={i} className="flex items-center gap-0.5 px-1.5 py-0.5 bg-green-900/30 text-green-400 text-label-sm rounded">
                        <Icon name="check_circle" className="text-[12px]" />
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {m.skillGaps.length > 0 && (
                <div className="flex flex-col gap-1">
                  <span className="text-label-sm text-on-surface-variant">Gaps</span>
                  <div className="flex flex-wrap gap-1">
                    {m.skillGaps.map((s, i) => (
                      <span key={i} className="px-1.5 py-0.5 bg-error/10 text-error text-label-sm rounded">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default JobMatchList;
