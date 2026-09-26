import React from 'react';
import { Icon } from '../common/Icon';

export interface OfflineBannerProps {
  isOnline: boolean;
  isChecking?: boolean;
  onRetry?: () => void;
}

export function OfflineBanner({ isOnline, isChecking = false, onRetry }: OfflineBannerProps) {
  if (isOnline) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 px-container-padding py-2 bg-error/10 border-b border-error/30 animate-fade-slide-in"
    >
      <Icon name="cloud_off" className="text-body-md text-error shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-label-md font-bold text-error leading-none">Server Unreachable</p>
        <p className="text-label-sm text-on-surface-variant mt-0.5">
          Scans and matching are paused until the connection is back.
        </p>
      </div>
      <button
        onClick={onRetry}
        disabled={isChecking}
        title="Check again now"
        className="flex items-center gap-1 px-2 py-1 rounded-lg text-label-md text-error hover:bg-error/10 disabled:opacity-60 transition-colors shrink-0"
      >
        <Icon name="refresh" className={`text-body-sm ${isChecking ? 'animate-spin' : ''}`} />
        Retry
      </button>
    </div>
  );
}

export default OfflineBanner;
