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
  /** No close control. Chrome's side panel chrome has its own X above this bar. */
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

  /**
   * Below this the marker's words are dropped and only the date is kept.
   *
   * Measured from the bar's own contents, which total roughly 500px with the
   * words (padding 32, logo and gap 30, brand 85, divider 13, icon 12, words
   * 118, date 104, controls 90) and roughly 380px without them. 420 sits
   * between the two: at that width the bar can show what is load-bearing and
   * not the sentence explaining it.
   *
   * A Chrome side panel drags down to about 320px, so this state is one the
   * reader reaches by dragging the edge, not a theoretical one.
   */
  const MARKER_WORDS_MIN_WIDTH = 420;

  const barRef = useRef<HTMLElement | null>(null);
  const [compact, setCompact] = useState(false);

  /**
   * Measure the bar rather than the viewport.
   *
   * The bar has its own padding and its own content, so the panel's width is
   * not the width the question is being asked about. A media query would also
   * have put this in CSS, where the suite could not exercise it — happy-dom
   * performs no layout — and this is behaviour a reader hits by dragging.
   */
  useEffect(() => {
    const el = barRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (typeof width === 'number') setCompact(width < MARKER_WORDS_MIN_WIDTH);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

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
    <header ref={barRef} data-role="top-app-bar" className="bg-surface-container w-full sticky top-0 z-40 border-b border-outline-variant/30 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)] flex justify-between items-center px-4 py-3 shrink-0">
      <div data-role="app-bar-brand" className="flex items-center gap-2 flex-1 min-w-0">
        {/* `shrink-0` because this is an inline SVG and so a flex item like any
            other: without it the mark compresses as the panel narrows, and a
            logo that resizes with the window reads as a rendering fault. */}
        <TrabaheroLogo size={22} className="text-accent-gradient shrink-0" />
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
            {/* The words are the first thing to go, not the date. Which is
                which matters: "Saved from job history" says what happened,
                and the date says when — but a reader who has just opened a
                scan knows which one they pressed, and only the date tells
                them the evidence behind it was retrieved then. */}
            {!compact && (
              <span className="text-label-sm text-on-surface-variant truncate">
                Saved from job history
              </span>
            )}
            <span className="text-label-sm text-on-surface-variant/70 shrink-0">
              {formatTimestamp(savedScan.timestamp)}
            </span>
          </div>
        )}
      </div>
      <div data-role="app-bar-actions" className="flex gap-3 relative shrink-0">
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
      </div>
    </header>
  );
}

export default TopAppBar;
