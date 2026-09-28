import React, { useState } from 'react';
import { Icon } from '../common';
import type { VerificationResult } from '../../types';

/**
 * TEMPORARY. Raw debug dump of the verification search and the prompt it
 * produced, so the retrieval -> prompt -> answer chain can be read directly
 * instead of inferred from the cards. Delete this file, the `debug_prompt`
 * field in the result event, and `debugPrompt` on VerificationResult once the
 * search behaviour is settled.
 */
export function SearchRawPanel({ result }: { result?: VerificationResult }) {
  const [open, setOpen] = useState(false);
  const raw = result?.debugPrompt;

  if (!raw) return null;

  const queries = result?.searchLog?.map((entry) => entry.query) ?? [];

  return (
    <div className="rounded-lg border border-outline-variant/30 bg-surface-container">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
      >
        <Icon name="search" className="text-secondary" />
        <span className="text-label-sm font-bold text-on-surface">Raw search dump (debug)</span>
        <Icon
          name="keyboard_arrow_down"
          className={`ml-auto text-on-surface-variant transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div className="flex flex-col gap-2 px-3 pb-3">
          {queries.length > 0 && (
            <div>
              <span className="text-label-sm font-bold text-on-surface-variant">Queries sent</span>
              <ul className="mt-1 flex flex-col gap-0.5">
                {queries.map((q, i) => (
                  <li key={i} className="text-label-sm text-on-surface-variant/90 break-all">
                    {i + 1}. {q}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <span className="text-label-sm font-bold text-on-surface-variant">
              Prompt as sent to the model
            </span>
            <pre className="mt-1 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded bg-surface-container-low p-2 text-label-sm text-on-surface font-mono leading-relaxed">
              {raw}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
