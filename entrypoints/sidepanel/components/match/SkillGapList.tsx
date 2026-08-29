import React from 'react';
import { Icon } from '../common/Icon';
import type { SkillGap } from '../../types';

export interface SkillGapListProps {
  gaps: SkillGap[];
  onAdd?: (id: string) => void;
}

export function SkillGapList({ gaps, onAdd }: SkillGapListProps) {
  return (
    <div className="flex flex-col gap-2 relative z-10">
      <span className="font-label-md text-on-surface">Skill Gaps ({gaps.length})</span>
      <div className="flex flex-wrap gap-2">
        {gaps.map((gap) => (
          <span
            key={gap.id}
            onClick={() => onAdd?.(gap.id)}
            className="px-2.5 py-1 bg-surface-container-high border border-outline-variant/30 text-on-surface-variant font-label-sm rounded-lg flex items-center gap-1 shadow-sm cursor-pointer hover:border-secondary/50 transition-colors"
          >
            <Icon name="add" className="text-[14px] text-secondary" />
            {gap.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export default SkillGapList;
