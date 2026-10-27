import React from 'react';
import { Icon } from '../common/Icon';
import { FormattedText } from '../common/FormattedText';
import type { ScannedJob, JobMatchItem } from '../../types';

export interface JobMatchListProps {
  jobs: ScannedJob[];
  matches: JobMatchItem[];
}

/**
 * The match score's ink and bar, one token per band.
 *
 * Theme-resolvable tokens, not the raw palette: `green-400`/`amber-400` were
 * authored for the dark theme and washed out on the light one. The bar takes the
 * same token as the number, so the two read as one status in either theme.
 */
function scoreColor(score: number): string {
  if (score >= 70) return 'text-secondary';
  if (score >= 40) return 'text-assessment-caution';
  return 'text-error';
}

function scoreBarColor(score: number): string {
  if (score >= 70) return 'bg-secondary';
  if (score >= 40) return 'bg-assessment-caution';
  return 'bg-error';
}

/**
 * The fit badge's chip class. The `chip-*` pair is the themed pale-fill /
 * saturated-ink treatment; a raw `bg-green-900/30 text-green-400` badge was
 * near-invisible in light mode, and `bg-error/10` generated nothing at all —
 * a custom token with an opacity variant silently produces no class.
 *
 * "Over" (more experience than asked) is informational, not a pass, so it takes
 * the neutral chip rather than green.
 */
function fitBadge(fit: string | undefined, type: 'experience' | 'industry'): string | null {
  if (!fit) return null;
  const lower = fit.toLowerCase();
  if (type === 'experience') {
    if (lower.includes('good') || lower.includes('fit')) return 'chip-verified';
    if (lower.includes('over')) return 'chip-stale';
    if (lower.includes('under')) return 'chip-caution';
  }
  if (type === 'industry') {
    if (lower.includes('strong')) return 'chip-verified';
    if (lower.includes('moderate')) return 'chip-caution';
    if (lower.includes('weak')) return 'chip-critical';
  }
  return 'chip-stale';
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
        const matchedSkills = m.matchedSkills ?? [];
        const skillGaps = m.skillGaps ?? [];
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
                <span className={`text-headline-xs font-headline font-bold ${scoreColor(m.score)}`}>
                  {m.score}%
                </span>
                <span className="text-label-sm text-on-surface-variant">
                  {m.label}
                </span>
              </div>
            </div>

            <div className="flex h-1.5 w-full bg-surface-variant rounded-full overflow-hidden shadow-inner">
              <div
                className={`h-full ${scoreBarColor(m.score)} rounded-full transition-all`}
                style={{ width: `${m.score}%` }}
              />
            </div>

            {m.reasoning && (
              <FormattedText text={m.reasoning} className="italic" />
            )}

            {(m.experienceFit || m.industryFit) && (
              <div className="flex flex-wrap gap-2">
                {m.experienceFit && (
                  <span className={`text-label-sm px-2 py-0.5 rounded ${fitBadge(m.experienceFit, 'experience')}`}>
                    Experience: {m.experienceFit}
                  </span>
                )}
                {m.industryFit && (
                  <span className={`text-label-sm px-2 py-0.5 rounded ${fitBadge(m.industryFit, 'industry')}`}>
                    Industry: {m.industryFit}
                  </span>
                )}
              </div>
            )}

            <div className="flex flex-wrap gap-4 text-body-sm">
              {matchedSkills.length > 0 && (
                <div className="flex flex-col gap-1">
                  <span className="text-label-sm text-on-surface-variant">Matched</span>
                  <div className="flex flex-wrap gap-1">
                    {matchedSkills.map((s, i) => (
                      <span key={i} className="flex items-center gap-0.5 px-1.5 py-0.5 chip-verified text-label-sm rounded">
                        <Icon name="check_circle" className="text-[12px]" />
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {skillGaps.length > 0 && (
                <div className="flex flex-col gap-1">
                  <span className="text-label-sm text-on-surface-variant">Gaps</span>
                  <div className="flex flex-wrap gap-1">
                    {skillGaps.map((s, i) => (
                      <span key={i} className="px-1.5 py-0.5 chip-critical text-label-sm rounded">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {m.recommendedActions && m.recommendedActions.length > 0 && (
              <div className="flex flex-col gap-1.5 mt-1 p-2.5 rounded-lg bg-surface-container-lowest border border-secondary/20">
                <span className="text-label-sm font-bold text-secondary flex items-center gap-1">
                  <Icon name="tips_and_updates" className="text-sm" />
                  Recommended Steps
                </span>
                <ul className="flex flex-col gap-1">
                  {m.recommendedActions.map((action, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-body-xs text-on-surface-variant">
                      <Icon name="arrow_right" className="text-[12px] text-secondary mt-0.5 shrink-0" />
                      {action}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default JobMatchList;
