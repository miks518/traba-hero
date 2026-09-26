import React from 'react';
import { Icon } from '../common';
import type { VerificationItem, IconName } from '../../types';

const STATUS_CONFIG: Record<VerificationItem['status'], { dot: string; bg: string; icon: IconName; label: string }> = {
  green: {
    dot: 'bg-green-500',
    bg: 'bg-green-500/10',
    icon: 'gpp_good',
    label: 'Found in results',
  },
  yellow: {
    dot: 'bg-secondary',
    bg: 'bg-secondary-container/10',
    icon: 'gpp_maybe',
    label: 'Not confirmed',
  },
  red: {
    dot: 'bg-error',
    bg: 'bg-error-container/10',
    icon: 'gpp_bad',
    label: 'Reported in results',
  },
};

interface VerificationCardProps {
  item: VerificationItem;
}

export function VerificationCard({ item }: VerificationCardProps) {
  const config = STATUS_CONFIG[item.status] || STATUS_CONFIG.yellow;

  return (
    <div className={`flex flex-col gap-1 p-2.5 rounded-lg ${config.bg}`}>
      <div className="flex items-center gap-2">
        <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${config.dot}`} />
        <span className="text-body-sm font-bold text-on-surface min-w-0">{item.label}</span>
        <span className={`text-label-sm font-bold px-1.5 py-0.5 rounded ml-auto shrink-0 ${
          item.status === 'green' ? 'bg-green-500/20 text-green-400' :
          item.status === 'yellow' ? 'bg-secondary/20 text-secondary' :
          'bg-error/20 text-error'
        }`}>
          {config.label}
        </span>
      </div>
      <p className="text-body-sm text-on-surface-variant leading-relaxed pl-5">
        {item.explanation}
      </p>
    </div>
  );
}
