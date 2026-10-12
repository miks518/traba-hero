import React, { useState, useRef, useEffect } from 'react';
import { FadeSlide } from '../common/FadeSlide';
import { Icon } from '../common/Icon';
import TrabaheroLogo from '../common/TrabaheroLogo';
import { formatTimestamp } from '../../lib/format';

export type TextSize = 'default' | 'big' | 'largest';

const TEXT_SIZE_OPTIONS: { value: TextSize; label: string }[] = [
  { value: 'default', label: 'Default' },
  { value: 'big', label: 'Big' },
  { value: 'largest', label: 'Largest' },
];

export interface TopAppBarProps {
  brandText?: string;
  onClose?: () => void;
  theme?: 'dark' | 'light';
  onToggleTheme?: () => void;
  textSize?: TextSize;
  onTextSizeChange?: (size: TextSize) => void;
  /**
   * Set while the panel is showing a scan reopened from history.
   *
   * The date is load-bearing. A reopened score was measured on that date, so a
   * reader deciding today is looking at evidence retrieved then. The marker
   * states when — it does not claim the result is still current, because the
   * panel cannot know that: a source page behind a `red` may have changed
   * since, and nothing here re-checks it.
   */
  savedScan?: { title: string; timestamp: string } | null;
}

export function TopAppBar({
  brandText = 'Trabahero',
  onClose,
  theme = 'dark',
  onToggleTheme,
  textSize = 'default',
  onTextSizeChange,
  savedScan,
}: TopAppBarProps) {
  const [showHelp, setShowHelp] = useState(false);
  const [showTextSize, setShowTextSize] = useState(false);
  const helpRef = useRef<HTMLDivElement>(null);
  const textSizeRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    if (!showTextSize) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (textSizeRef.current && !textSizeRef.current.contains(e.target as Node)) {
        setShowTextSize(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showTextSize]);

  return (
    <header data-role="top-app-bar" className="bg-surface-container w-full sticky top-0 z-40 border-b border-outline-variant/30 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)] flex justify-between items-center px-4 py-3 shrink-0">
      <div className="flex items-center gap-2 min-w-0">
        <TrabaheroLogo size={22} className="text-accent-gradient" />
        <span className="text-headline-sm font-headline font-bold text-accent-gradient shrink-0">
          {brandText}
        </span>
        {/* Beside the brand, on the same row. A second line would reflow a bar
            of fixed height every time a scan was opened, which reads as the
            panel jumping. The title is not shown: the reader has this very scan
            on screen, so the marker names where it came from and when. */}
        {savedScan && (
          <div
            role="status"
            data-role="saved-scan-marker"
            className="flex items-center gap-1.5 min-w-0 pl-2 ml-1 border-l border-outline-variant/40"
          >
            <Icon name="history" className="text-xs text-on-surface-variant shrink-0" />
            <span className="text-label-sm text-on-surface-variant truncate">
              Saved from job history
            </span>
            <span className="text-label-sm text-on-surface-variant/70 font-mono shrink-0">
              {formatTimestamp(savedScan.timestamp)}
            </span>
          </div>
        )}
      </div>
      <div className="flex gap-3 relative">
        {onTextSizeChange && (
          <div ref={textSizeRef}>
            <Icon
              name="text_fields"
              className="cursor-pointer text-on-surface-variant hover:text-secondary transition-colors active:scale-95"
              onClick={() => { setShowTextSize((p) => !p); setShowHelp(false); }}
            />
            <FadeSlide
              show={showTextSize}
              className="absolute right-0 top-full mt-2 w-44 p-2 rounded-xl bg-surface-container-high border border-outline-variant/30 shadow-xl z-50"
            >
              <div className="text-label-md font-bold text-on-surface-variant px-2 py-1 mb-1">Text Size</div>
              {TEXT_SIZE_OPTIONS.map((opt) => (
                <div
                  key={opt.value}
                  role="radio"
                  aria-checked={textSize === opt.value}
                  className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg cursor-pointer hover:bg-surface-container-highest/60 transition-colors"
                  onClick={() => { onTextSizeChange?.(opt.value); setShowTextSize(false); }}
                >
                  <span
                    className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
                      textSize === opt.value
                        ? 'border-secondary bg-secondary'
                        : 'border-outline'
                    }`}
                  >
                    {textSize === opt.value && (
                      <span className="w-1.5 h-1.5 rounded-full bg-on-secondary" />
                    )}
                  </span>
                  <span className="text-body-sm text-on-surface">{opt.label}</span>
                </div>
              ))}
            </FadeSlide>
          </div>
        )}
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
          <FadeSlide
            show={showHelp}
            className="absolute right-0 top-full mt-2 w-72 p-4 rounded-xl bg-surface-container-high border border-outline-variant/30 shadow-xl z-50 text-body-sm text-on-surface"
          >
            <div className="font-headline-md font-bold mb-2 text-secondary">
              How to Use Trabahero
            </div>
            <ol className="list-decimal list-inside space-y-1.5">
              <li>Click <strong>Pick a Job Post</strong> to select an area on the page</li>
              <li>Add up to 4 screenshots by picking more areas or using manual crop</li>
              <li>Click <strong>Scan All</strong> to check for scam indicators</li>
              <li>Switch to <strong>Match</strong> to compare job posts with your resume</li>
            </ol>
          </FadeSlide>
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
