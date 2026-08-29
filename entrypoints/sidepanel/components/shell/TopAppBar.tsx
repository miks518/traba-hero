import React, { useState, useRef, useEffect } from 'react';
import { Icon } from '../common/Icon';
import TrabaheroLogo from '../common/TrabaheroLogo';

export interface TopAppBarProps {
  brandText?: string;
  onClose?: () => void;
  theme?: 'dark' | 'light';
  onToggleTheme?: () => void;
}

export function TopAppBar({
  brandText = 'Trabahero',
  onClose,
  theme = 'dark',
  onToggleTheme,
}: TopAppBarProps) {
  const [showHelp, setShowHelp] = useState(false);
  const helpRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showHelp) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (helpRef.current && !helpRef.current.contains(e.target as Node)) {
        setShowHelp(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showHelp]);

  return (
    <header className="bg-surface-container w-full sticky top-0 z-20 border-b border-outline-variant/30 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)] flex justify-between items-center px-4 py-3 shrink-0">
      <div className="flex items-center gap-2">
        <TrabaheroLogo size={22} className="text-gold-gradient" />
        <span className="text-headline-sm font-headline font-bold text-gold-gradient">
          {brandText}
        </span>
      </div>
      <div className="flex gap-3 relative">
        {onToggleTheme && (
          <Icon
            name={theme === 'dark' ? 'light_mode' : 'dark_mode'}
            className="cursor-pointer text-on-surface-variant hover:text-secondary transition-colors active:scale-95"
            onClick={onToggleTheme}
          />
        )}
        <div ref={helpRef}>
          <Icon
            name="help"
            className="cursor-pointer text-on-surface-variant hover:text-secondary transition-colors active:scale-95"
            onClick={() => setShowHelp((p) => !p)}
          />
          {showHelp && (
            <div className="absolute right-0 top-full mt-2 w-72 p-4 rounded-xl bg-surface-container-high border border-outline-variant/30 shadow-xl z-50 text-body-sm text-on-surface">
              <div className="font-headline-md font-bold mb-2 text-secondary">
                How to Use Trabahero
              </div>
              <ol className="list-decimal list-inside space-y-1.5">
                <li>Click <strong>Pick a Job Post</strong> to select an area on the page</li>
                <li>Add up to 4 screenshots by picking more areas or using manual crop</li>
                <li>Click <strong>Scan All</strong> to check for scam indicators</li>
                <li>Switch to <strong>Match</strong> to compare job posts with your resume</li>
              </ol>
            </div>
          )}
        </div>
        <Icon
          name="close"
          className="cursor-pointer text-on-surface-variant hover:text-secondary transition-colors active:scale-95"
          onClick={onClose}
        />
      </div>
    </header>
  );
}

export default TopAppBar;
