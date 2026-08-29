import React from 'react';
import { Icon } from '../common/Icon';
import type { RedFlag } from '../../types';

export interface RedFlagCardProps {
  flag: RedFlag;
}

const SEVERITY_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  high: { bg: 'bg-error/20', text: 'text-error', border: 'border-error/30' },
  mid: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30' },
  low: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/30' },
};

export function RedFlagCard({ flag }: RedFlagCardProps) {
  const sev = SEVERITY_STYLES[flag.severity || 'mid'] || SEVERITY_STYLES.mid;
  return (
    <div className="bg-surface-container-low border border-outline-variant/10 rounded-lg p-3 flex gap-3 tactile-card hover:bg-surface-container transition-colors">
      <div className={`${sev.bg} ${sev.text} h-8 w-8 rounded-full flex items-center justify-center shrink-0 border ${sev.border}`}>
        <Icon name={flag.icon} className="text-sm" />
      </div>
      <div className="flex flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <h4 className="font-label-md text-on-surface font-bold">{flag.title}</h4>
          {flag.severity && (
            <span className={`text-[10px] font-label uppercase px-1.5 py-0.5 rounded ${sev.bg} ${sev.text}`}>
              {flag.severity}
            </span>
          )}
        </div>
        <p className="font-label-sm text-on-surface-variant leading-tight">{flag.description}</p>
      </div>
    </div>
  );
}

export default RedFlagCard;
