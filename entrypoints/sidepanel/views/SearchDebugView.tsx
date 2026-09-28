import React, { useCallback, useRef, useState } from 'react';
import { Icon } from '../components/common';
import { debugSearchStream, type DebugSearchItem, type DebugSearchStep } from '../lib/api';

const SUGGESTIONS = [
  'Jollibee Philippines',
  'Caishen Marketing Services Inc Philippines',
  'Vikings Philippines',
  'McDonalds Philippines',
];

/**
 * TEMPORARY. A console for the backend web search: type a query, see every
 * engine tried, what each returned, and what the production path concluded.
 *
 * Built because a rate-limited engine was answering with a cached page from an
 * unrelated query — a wrong-but-successful response that no status code or
 * result count reveals. This panel is where that is visible. Delete with the
 * 'search' nav tab, /api/debug/search, and debugSearchStream in api.ts.
 */
export function SearchDebugView() {
  const [query, setQuery] = useState('');
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<DebugSearchStep[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const onStep = useCallback((step: DebugSearchStep) => {
    setSteps((prev) => [...prev, step]);
  }, []);

  const run = useCallback(async () => {
    const q = query.trim();
    if (!q || running) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setSteps([]);
    setRunning(true);
    try {
      await debugSearchStream(q, onStep, controller.signal, 5);
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }, [query, running, onStep]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const outcome = steps.find((s) => s.kind === 'outcome');
  const meta = steps.find((s) => s.kind === 'meta');
  const failed = steps.find((s) => s.kind === 'error');

  return (
    <div className="h-full flex flex-col gap-3 p-4 overflow-y-auto custom-scroll">
      <div className="flex items-center gap-2">
        <Icon name="search" className="text-secondary" />
        <h2 className="text-label-md font-bold text-on-surface">Search Debug</h2>
        {running && (
          <span className="ml-auto flex items-center gap-1.5 text-label-sm text-on-surface-variant">
            <span className="w-2 h-2 rounded-full bg-secondary animate-ping" />
            Searching…
          </span>
        )}
      </div>

      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !running) void run(); }}
          placeholder="Search query…"
          disabled={running}
          className="flex-1 px-2 py-1.5 rounded-lg bg-surface-container border border-outline-variant/30 text-body-sm text-on-surface placeholder:text-on-surface-variant/60 focus:outline-none focus:border-secondary disabled:opacity-50"
        />
        {running ? (
          <button
            type="button"
            onClick={cancel}
            className="px-3 py-1.5 rounded-lg bg-error-container text-on-error text-label-md font-bold"
          >
            Stop
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void run()}
            disabled={!query.trim()}
            className="px-3 py-1.5 rounded-lg bg-secondary text-on-secondary text-label-md font-bold disabled:opacity-40"
          >
            Search
          </button>
        )}
      </div>

      {!steps.length && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-surface-container-low border border-outline-variant/20">
            <p className="text-body-sm text-on-surface-variant leading-relaxed">
              Sends one query to Tavily and streams the result: every hit with its URL, then the
              provider's raw response body. Production issues one query per verification — the same
              &ldquo;{'<company>'} Philippines&rdquo; shape these suggestions use. No AI call is made.
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-label-sm font-bold text-on-surface-variant">Try one</span>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setQuery(s)}
                className="text-left text-label-sm text-secondary hover:underline break-all"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {meta && (
        <div className="p-2 rounded-lg bg-surface-container-low border border-outline-variant/20">
          <div className="text-label-sm text-on-surface-variant">
            <span className="font-bold">provider</span> {meta.provider}
          </div>
          <div className="text-label-sm text-on-surface-variant">
            <span className="font-bold">api key</span>{' '}
            {meta.keyConfigured ? 'configured' : 'MISSING — searches will report as failed'}
          </div>
          <div className="text-label-sm text-on-surface-variant">
            <span className="font-bold">max results</span> {meta.maxResults}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <span className="text-label-sm font-bold text-on-surface-variant">Process</span>
        {steps.map((step, i) => <StepRow key={i} step={step} />)}
      </div>

      {outcome && (
        <div className="flex flex-col gap-2">
          <span className="text-label-sm font-bold text-on-surface-variant">Production result</span>
          <div
            className={`p-3 rounded-lg border text-body-sm ${
              outcome.ok ? 'bg-surface-container-low border-outline-variant/20' : 'bg-error-container/10 border-error/40'
            }`}
          >
            <div className="text-on-surface">
              {/*
                A successful search with no results is NOT a failure — the
                company may simply have no online footprint. The two states
                must stay visibly distinct, because collapsing them is the
                defect the rebuild exists to remove.
              */}
              <span className="font-bold">
                {!outcome.ok
                  ? 'Search FAILED'
                  : outcome.count === 0
                    ? 'Search succeeded, found nothing'
                    : 'Results returned'}
              </span>
              {' · '}
              {outcome.count} result{outcome.count === 1 ? '' : 's'}
              {' · '}
              {outcome.latency}s
              {typeof outcome.creditsUsed === 'number' ? ` · ${outcome.creditsUsed} credit(s)` : ''}
            </div>
            {outcome.error && (
              <div className="mt-1 text-label-sm text-on-surface-variant break-words">{outcome.error}</div>
            )}
          </div>
        </div>
      )}

      {failed && (
        <div className="p-3 rounded-lg bg-error-container/10 border border-error/40">
          <span className="text-body-sm text-on-surface break-words">{failed.error}</span>
        </div>
      )}
    </div>
  );
}

function StepRow({ step }: { step: DebugSearchStep }) {
  const cls = 'text-label-sm px-2 py-1 rounded font-mono';

  switch (step.kind) {
    case 'result':
      return <ResultCard item={step.item} />;
    case 'raw':
      return (
        <details className="p-2 rounded bg-surface-container border border-outline-variant/20">
          <summary className={`${cls} cursor-pointer bg-surface-container-high text-on-surface`}>
            raw provider response ({step.body.length} chars)
          </summary>
          <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words text-label-sm text-on-surface">
            {step.body}
          </pre>
        </details>
      );
    default:
      return null;
  }
}

function ResultCard({ item }: { item: DebugSearchItem }) {
  return (
    <div className="flex flex-col gap-1 p-2.5 rounded-lg bg-surface-container-low border border-outline-variant/20">
      <div className="flex items-start gap-2">
        {typeof item.score === 'number' && (
          <span className="text-[10px] font-mono px-1 py-0.5 rounded bg-surface-container-high text-on-surface-variant shrink-0 mt-0.5">
            {item.score.toFixed(2)}
          </span>
        )}
        <span className="text-body-sm font-bold text-on-surface min-w-0 break-words">{item.title}</span>
      </div>
      {item.url && (
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="text-label-sm text-secondary hover:underline break-all pl-1"
        >
          {item.url}
        </a>
      )}
      {item.snippet && (
        <p className="text-body-sm text-on-surface-variant leading-relaxed break-words pl-1">{item.snippet}</p>
      )}
    </div>
  );
}

export default SearchDebugView;
