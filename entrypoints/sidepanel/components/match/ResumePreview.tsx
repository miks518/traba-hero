import React from 'react';
import { Icon } from '../common/Icon';
import type { ResumeData } from '../../types';

export interface ResumePreviewProps {
  data: ResumeData;
  onRemove?: () => void;
}

export function ResumePreview({ data, onRemove }: ResumePreviewProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="font-label-md text-on-surface-variant uppercase tracking-wider text-[11px]">
          Resume Summary
        </span>
        <div className="flex gap-2">
          <button
            onClick={onRemove}
            title="Remove resume"
            className="p-1 rounded-lg text-error hover:bg-error/10 transition-colors"
          >
            <Icon name="delete" className="text-[18px]" />
          </button>
        </div>
      </div>
      <div className="tactile-card p-4 bg-surface-container border border-outline-variant/30 rounded-xl flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Icon name="work" className="text-secondary text-sm" />
          <span className="font-body-md text-on-surface">
            {data.job_titles.join(', ') || 'N/A'}
          </span>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {data.skills.map((s, i) => (
            <span
              key={i}
              className="px-2 py-0.5 bg-secondary/10 border border-secondary/20 text-secondary text-label-sm rounded-lg"
            >
              {s}
            </span>
          ))}
        </div>

        <div className="flex gap-4 text-body-sm text-on-surface-variant">
          <span>{data.experience_years > 0 ? `${data.experience_years} years exp` : ''}</span>
          {data.industries.length > 0 && (
            <span>{data.industries.join(', ')}</span>
          )}
        </div>

        {data.summary && (
          <p className="text-body-sm text-on-surface-variant/80 leading-relaxed">
            {data.summary}
          </p>
        )}
      </div>
    </div>
  );
}

export default ResumePreview;
