import React from 'react';
import { Icon } from '../common/Icon';
import { RedFlagCard } from './RedFlagCard';
import type { RedFlag } from '../../types';

export interface RedFlagsListProps {
  flags: RedFlag[];
  critical: boolean;
}

export function RedFlagsList({ flags, critical }: RedFlagsListProps) {
  if (flags.length === 0) return null;
  return (
    <section className="flex flex-col gap-stack-sm">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Icon name="flag" className="text-error text-sm" />
          <h3 className="font-headline-md text-lg text-error font-bold">
            Red Flags ({flags.length})
          </h3>
        </div>
        {critical && (
          <span className="bg-error text-on-error px-2 py-0.5 rounded-full font-label-sm text-[10px] font-bold">
            CRITICAL
          </span>
        )}
      </div>
      {flags.map((flag) => (
        <RedFlagCard key={flag.id} flag={flag} />
      ))}
    </section>
  );
}

export default RedFlagsList;
