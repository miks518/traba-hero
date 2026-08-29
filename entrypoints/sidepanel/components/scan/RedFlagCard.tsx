import React from 'react';
import { Icon } from '../common/Icon';
import type { RedFlag } from '../../types';

export interface RedFlagCardProps {
  flag: RedFlag;
}

export function RedFlagCard({ flag }: RedFlagCardProps) {
  return (
    <div className="bg-surface-container-low border border-outline-variant/10 rounded-lg p-3 flex gap-3 tactile-card hover:bg-surface-container transition-colors">
      <div className="bg-error/20 text-error h-8 w-8 rounded-full flex items-center justify-center shrink-0 border border-error/30">
        <Icon name={flag.icon} className="text-sm" />
      </div>
      <div>
        <h4 className="font-label-md text-on-surface font-bold">{flag.title}</h4>
        <p className="font-label-sm text-on-surface-variant leading-tight">{flag.description}</p>
      </div>
    </div>
  );
}

export default RedFlagCard;
