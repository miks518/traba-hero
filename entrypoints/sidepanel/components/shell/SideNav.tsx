import React from 'react';
import { Icon } from '../common/Icon';
import { NAV_TABS, BOTTOM_NAV_ICONS } from '../../data/content';
import type { ScanProgress } from '../../lib/api';
import type { ViewId } from '../../types';

export interface SideNavProps {
  activeView: ViewId;
  onTabClick?: (id: ViewId) => void;
  scannedJobsCount?: number;
  scanningProgress?: ScanProgress | null;
  isLocked?: boolean;
}

export function SideNav({ activeView, onTabClick, scannedJobsCount = 0, scanningProgress, isLocked }: SideNavProps) {
  return (
    <nav className="h-full w-20 flex flex-col items-center py-4 bg-surface-container-low border-r border-outline-variant/20 shrink-0">
      <div className="flex flex-col gap-6">
        {NAV_TABS.map((tab) => {
          const isActive = activeView === tab.id;
          const showLock = isLocked && tab.id === 'match';
          return (
            <button
              key={tab.id}
              title={showLock ? `${tab.title} (locked — scam detected)` : tab.title}
              onClick={() => onTabClick?.(tab.id)}
              className={`flex flex-col items-center justify-center rounded-xl p-3 cursor-pointer transition-all duration-300 ease-out active:translate-y-[1px] ${
                isActive
                  ? 'nav-item-active'
                  : 'text-on-surface-variant opacity-70 hover:bg-surface-container-high'
              }`}
            >
              <div className="relative">
                <Icon name={tab.icon} filled={isActive} />
                {showLock && (
                  <Icon
                    name="lock"
                    className="absolute -bottom-1 -right-1 text-[10px] text-error bg-background rounded-full"
                  />
                )}
              </div>
              <span
                className={`text-[10px] mt-1 font-label ${
                  isActive ? 'font-bold' : ''
                }`}
              >
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>

      <div className="mt-auto flex flex-col gap-6 items-center">
        {BOTTOM_NAV_ICONS.map((iconName) => (
          <Icon
            key={iconName}
            name={iconName}
            title={iconName === 'close' ? 'Close panel' : 'Help'}
            onClick={iconName === 'close' ? () => window.close() : undefined}
            className="text-on-surface-variant hover:text-secondary cursor-pointer transition-colors"
          />
        ))}

        {scannedJobsCount > 0 && (
          <div className="flex items-center gap-1 text-[10px] font-label text-on-surface-variant">
            <Icon name="work" className="text-xs" />
            <span>{scannedJobsCount}</span>
          </div>
        )}

        {scanningProgress && (
          <div className="flex items-center gap-1.5 text-secondary">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-ping" />
            <span className="text-[10px] font-label">Scanning… {scanningProgress.percent}%</span>
          </div>
        )}
      </div>
    </nav>
  );
}

export default SideNav;
