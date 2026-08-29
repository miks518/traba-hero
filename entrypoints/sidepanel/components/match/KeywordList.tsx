import React from 'react';
import { Icon } from '../common/Icon';
import type { MatchKeyword } from '../../types';

export interface KeywordListProps {
  keywords: MatchKeyword[];
}

export function KeywordList({ keywords }: KeywordListProps) {
  return (
    <div className="tactile-card bg-surface-container-low border border-outline-variant/30 rounded-xl p-4">
      <span className="font-label-md text-on-surface mb-3 block">
        Top Match Keywords
      </span>
      <div className="flex flex-col gap-3">
        {keywords.map((keyword, idx) => (
          <div
            key={keyword.id}
            className={`flex justify-between items-center py-1 ${
              idx < keywords.length - 1 ? 'border-b border-outline-variant/10' : ''
            }`}
          >
            <span className="font-body-md text-on-surface-variant">{keyword.label}</span>
            {keyword.matched && (
              <Icon name="check_circle" filled className="text-secondary text-[20px]" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default KeywordList;
