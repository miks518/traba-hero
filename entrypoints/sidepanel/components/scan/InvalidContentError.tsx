import React from 'react';
import { Icon } from '../common/Icon';

export interface InvalidContentErrorProps {
  onRetry?: () => void;
}

export function InvalidContentError({ onRetry }: InvalidContentErrorProps) {
  return (
    <section className="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-6 flex flex-col items-center text-center tactile-card mx-auto w-full max-w-sm">
      <div className="relative mb-5">
        <div className="w-28 h-28 rounded-full bg-[#0d0e12] flex items-center justify-center border border-white/[0.05]"
          style={{ boxShadow: 'inset 4px 4px 8px rgba(0,0,0,0.6), inset -2px -2px 6px rgba(255,255,255,0.03)' }}>
          <Icon name="warning" className="text-5xl text-secondary animate-pulse" filled />
        </div>
        <div className="absolute -inset-5 rounded-full opacity-20 pointer-events-none"
          style={{ background: 'radial-gradient(circle, rgba(233,195,73,0.3) 0%, transparent 70%)' }} />
      </div>

      <h2 className="text-headline-sm font-headline text-on-surface mb-2">
        Scanning Interrupted
      </h2>
      <p className="text-body-sm text-on-surface-variant max-w-xs mx-auto mb-5">
        We couldn't detect a job listing. Please ensure that the screenshot contains a valid job listing and try again.
      </p>

    </section>
  );
}

export default InvalidContentError;
