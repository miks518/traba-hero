import React from 'react';

export interface FormattedTextProps {
  text: string;
  className?: string;
}

export function FormattedText({ text, className = '' }: FormattedTextProps) {
  if (!text) return null;

  const lines = text.split('\n').filter((l) => l.trim());

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
          return (
            <div key={i} className="flex items-start gap-1.5 text-body-sm text-on-surface-variant">
              <span className="text-secondary mt-0.5 shrink-0">•</span>
              <span>{trimmed.replace(/^[-•]\s*/, '')}</span>
            </div>
          );
        }
        return (
          <p key={i} className="text-body-sm text-on-surface-variant leading-relaxed text-left">
            {trimmed}
          </p>
        );
      })}
    </div>
  );
}

export default FormattedText;
