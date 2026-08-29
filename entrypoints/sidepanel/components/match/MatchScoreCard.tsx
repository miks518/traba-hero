import React from 'react';
import { SkillGapList } from './SkillGapList';
import type { SkillGap } from '../../types';

export interface MatchScoreCardProps {
  score: number;
  compatibilityLabel: string;
  skillGaps: SkillGap[];
  onAddGap?: (id: string) => void;
}

export function MatchScoreCard({
  score,
  compatibilityLabel,
  skillGaps,
  onAddGap,
}: MatchScoreCardProps) {
  return (
    <div className="tactile-card p-4 bg-secondary-container/10 border border-secondary/20 rounded-xl relative overflow-hidden shadow-lg">
      <div className="absolute -top-12 -right-12 w-32 h-32 bg-secondary opacity-10 blur-3xl rounded-full"></div>

      <div className="flex items-end justify-between relative z-10 mb-4">
        <div className="flex flex-col">
          <span className="font-label-sm text-secondary uppercase font-bold tracking-tighter">
            Match Score
          </span>
          <h2 className="text-[40px] leading-none text-gold-gradient font-extrabold mt-1">
            {score}%
          </h2>
        </div>
        <div className="flex flex-col items-end">
          <span className="font-label-sm text-on-surface-variant">
            {compatibilityLabel}
          </span>
          <div className="flex h-1.5 w-24 bg-surface-variant rounded-full mt-2 overflow-hidden shadow-inner">
            <div
              className="h-full bg-secondary"
              style={{ width: `${score}%` }}
            />
          </div>
        </div>
      </div>

      <SkillGapList gaps={skillGaps} onAdd={onAddGap} />
    </div>
  );
}

export default MatchScoreCard;
