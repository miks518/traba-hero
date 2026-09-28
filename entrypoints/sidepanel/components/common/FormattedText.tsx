import React from 'react';

export interface FormattedTextProps {
  text: string;
  className?: string;
  /**
   * Applied to every rendered line — paragraphs and bullet bodies alike. The
   * default is the panel's body style; pass an override where a block needs its
   * own weight, such as the verdict in `PostingAnalysis` reading a step larger
   * than every other prose the panel writes.
   */
  bodyClassName?: string;
  /** The bullet glyph only, not the text beside it. */
  bulletClassName?: string;
}

const DEFAULT_BODY = 'text-body-sm text-on-surface-variant';
const DEFAULT_BULLET = 'text-secondary mt-0.5 shrink-0';

export function FormattedText({
  text,
  className = '',
  bodyClassName = DEFAULT_BODY,
  bulletClassName = DEFAULT_BULLET,
}: FormattedTextProps) {
  if (!text) return null;

  const lines = text.split('\n').filter((l) => l.trim());

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
          return (
            <div key={i} className={`flex items-start gap-1.5 ${bodyClassName}`}>
              <span className={bulletClassName}>•</span>
              <span>{trimmed.replace(/^[-•]\s*/, '')}</span>
            </div>
          );
        }
        return (
          <p key={i} className={`${bodyClassName} leading-relaxed text-left`}>
            {trimmed}
          </p>
        );
      })}
    </div>
  );
}

export default FormattedText;
