import React from 'react';
import { RedFlagCard } from './RedFlagCard';
import type { RedFlag } from '../../types';

export interface RedFlagsListProps {
  flags: RedFlag[];
  critical: boolean;
}

export function RedFlagsList({ flags, critical }: RedFlagsListProps) {
  return (
    <section className="flex flex-col gap-stack-sm">
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-headline-md text-lg text-on-surface">
          Red Flags ({flags.length})
        </h3>
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
