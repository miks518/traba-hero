import React from 'react';
import { Icon } from '../common/Icon';

export interface ResumeCardProps {
  filename: string;
  lastUpdated: string;
  onEdit?: () => void;
}

export function ResumeCard({ filename, lastUpdated, onEdit }: ResumeCardProps) {
  return (
    <section className="flex flex-col gap-3">
      <span className="font-label-md text-on-surface-variant uppercase tracking-wider text-[11px]">
        Active Resume
      </span>
      <div className="tactile-card p-4 bg-surface-container border border-outline-variant/30 rounded-xl flex items-center gap-3 relative overflow-hidden">
        <div className="w-10 h-10 rounded bg-secondary-container flex items-center justify-center text-on-secondary-container">
          <Icon name="picture_as_pdf" />
        </div>
        <div className="flex flex-col overflow-hidden">
          <span className="font-label-md truncate">{filename}</span>
          <span className="font-label-sm text-on-surface-variant">
            Last updated: {lastUpdated}
          </span>
        </div>
        <button
          onClick={onEdit}
          className="ml-auto p-1 text-outline hover:text-secondary transition-colors"
        >
          <Icon name="edit" className="text-[18px]" />
        </button>
      </div>
    </section>
  );
}

export default ResumeCard;
