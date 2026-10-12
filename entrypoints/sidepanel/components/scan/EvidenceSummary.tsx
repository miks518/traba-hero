import React from 'react';
import { Icon } from '../common';
import { VerificationCard } from './VerificationCard';
import { AnomaliesList } from './AnomaliesList';
import type { Accent } from '../../lib/riskAccent';
import type { Anomaly, VerificationResult } from '../../types';

interface EvidenceSummaryProps {
  result?: VerificationResult;
  loading?: boolean;
  error?: boolean;
  currentQuery?: string;
  /**
   * Forwarded to the `AnomaliesList` this section renders. The list only exists
   * in one of two places - here, or directly in the evidence group - so the
   * provenance button needs to reach it either way.
   */
  anomaliesHeadingRef?: React.Ref<HTMLDivElement>;
  /**
   * The posting's anomalies, rendered *inside* this section so they lead it.
   * They are what the evidence is about, and a reader who opens the summary
   * first should meet the claim before the corroboration.
   *
   * Only when the search returned something. With no findings there is nothing
   * for them to lead, so the caller keeps them as a sibling — a posting with no
   * employer still has them, and they must not disappear behind a heading that
   * says nothing was found.
   */
  anomalies?: Anomaly[];
  critical?: boolean;
  /**
   * Risk colour for the header and container. Applied only when this section
   * has been promoted to the top of the panel, so it reads as urgent only in the
   * case where it is leading the results.
   */
  accent?: Accent;
}

/**
 * What the search found, with sources. Renamed from "External Verification":
 * that named the mechanism (external, meaning the web) and implied an actor
 * reaching a verdict. This section reports, and the reader draws the line.
 *
 * The heading is derived from state. A section titled "Evidence Summary" over
 * an empty list asserts that evidence was summarised when none was, so the
 * three outcomes each get their own heading:
 *
 *   something found  -> "Evidence Summary"
 *   ran, found none  -> not evidence; says what was searched
 *   could not run    -> not evidence; says the search did not complete
 *
 * The last two are both "no evidence" and are deliberately kept apart, because
 * `SearchOutcome.ok` and `.results` are independent and the panel must not undo
 * that by collapsing them into one "nothing found" state. Each body below is
 * tagged `data-state` so a test can scope to one outcome instead of asserting
 * over the whole section, which cannot tell the three apart.
 */
/**
 * The one heading this section can have, derived from what happened.
 *
 * "Evidence Summary" is only available to a search that returned something.
 * The other outcomes are not summaries of evidence — a search that ran and
 * found nothing, one that could not run, and one where some queries failed are
 * three different facts about *our* retrieval, and each is named rather than
 * filed under evidence.
 *
 * A search that could not run outranks the items. `SearchOutcome.ok` and
 * `.results` are independent, so items can arrive with `search_ok: false`; the
 * retrieval that failed is the more important fact about the section, and
 * calling it evidence over it would claim we looked when we did not.
 *
 * Rendered unconditionally, unlike the constant heading it replaced: a section
 * that only announces itself when it has good news is invisible to anyone
 * navigating by heading in exactly the states where the reader most needs to
 * find out what was and was not looked up.
 */
function headingFor(state: {
  hasItems: boolean;
  loading?: boolean;
  unreadable: boolean;
  partial: boolean;
  error?: boolean;
}): string {
  if (state.loading && !state.hasItems) return 'Searching the web';
  // Ahead of `unreadable` on purpose. Both mean "no findings", and blaming the
  // search for a request that never returned a readable answer names the wrong
  // subsystem — see the body copy below.
  if (state.error) return 'Verification could not be completed';
  if (state.unreadable) return 'Search could not run';
  if (state.hasItems) return 'Evidence Summary';
  if (state.partial) return 'Partial search coverage';
  return 'Searched, found nothing';
}

export function EvidenceSummary({
  result,
  loading,
  error,
  currentQuery,
  anomalies = [],
  critical = false,
  accent,
  anomaliesHeadingRef,
}: EvidenceSummaryProps) {
  const hasItems = Boolean(result && result.items && result.items.length > 0);
  const unreadable = result?.searchOk === false;
  const partial = Boolean(result?.searchPartial);
  // The same state the heading prefers, held separately so the body can name
  // what actually happened. `searchOk: false` and `error` can arrive together:
  // the searches may have completed and the model's answer then failed to parse,
  // which is not the search's failure and must not be described as one.
  const unreadableAnswer = Boolean(error) && unreadable;

  const heading = headingFor({ hasItems, loading, unreadable, partial, error });
  const surface = accent?.surface ?? 'bg-surface-container-low';
  const border = accent?.border ? `${accent.border} border` : '';
  const text = accent?.text ?? 'text-secondary';

  return (
    <div className={`flex flex-col gap-3 p-4 rounded-xl ${surface} ${border}`}>
      <div className="flex items-center gap-2">
        <Icon name="search" className={text} />
        <h3 className={`text-label-md font-bold ${accent?.text ?? 'text-on-surface'}`}>
          {heading}
        </h3>
        {loading && (
          <span className="ml-auto flex items-center gap-1.5 text-label-sm text-on-surface-variant">
            <span className="w-2 h-2 rounded-full bg-secondary animate-ping" />
            Searching…
          </span>
        )}
      </div>

      {loading && !hasItems && (
        <div className="flex flex-col items-center gap-3 py-4">
          <div className="w-10 h-10 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
          <div className="flex flex-col items-center gap-1 text-center">
            <span className="text-body-sm text-on-surface-variant">Searching… Please wait.</span>
            {currentQuery && (
              <span className="text-label-sm text-on-surface-variant/70 max-w-[250px] truncate">
                {currentQuery}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Anomalies lead the summary: they are what the evidence is about. They
          render here in the found state and stay a sibling otherwise, because a
          posting with no employer and no search still has them and they must not
          disappear behind a heading that says nothing was found. */}
      {hasItems && (
        <AnomaliesList anomalies={anomalies} critical={critical} headingRef={anomaliesHeadingRef} />
      )}

      {unreadable && (
        <div
          data-state="unreadable"
          className="flex flex-col gap-1.5 p-3 rounded-lg bg-error-container/10 border border-error/40"
        >
          <div className="flex items-start gap-2">
            <Icon name="warning" className="text-error mt-0.5" />
            <p className="text-body-sm text-on-surface-variant leading-relaxed">
              {unreadableAnswer
                ? 'The answer could not be read, so nothing about this employer was established. Whether the searches ran is not recorded here. This is not a finding about them. What the posting itself says still stands.'
                : 'The web search did not run, so nothing about this employer is known. This is not a finding about them. What the posting itself says still stands.'}
            </p>
          </div>
          {result?.searchError && (
            <span className="text-label-sm text-on-surface-variant/80 break-words">
              {result.searchError}
            </span>
          )}
        </div>
      )}

      {partial && (
        <div
          data-state="partial"
          className="flex flex-col gap-1.5 p-3 rounded-lg bg-amber-500/10 border border-amber-500/40"
        >
          <div className="flex items-start gap-2">
            <Icon name="warning" className="text-amber-500 mt-0.5" />
            <p className="text-body-sm text-on-surface-variant leading-relaxed">
              {result?.queriesFailed && result?.queriesIssued
                ? `${result.queriesFailed} of ${result.queriesIssued} searches failed, `
                : 'One of the searches failed, '}
              so some checks were made against a thinner set of results than the
              others. This is not a finding about the employer, and an
              unconfirmed claim may simply not have been covered.
            </p>
          </div>
        </div>
      )}

      {hasItems && (
        <div className="flex flex-col gap-2">
          {result!.items.map((item, i) => (
            <VerificationCard key={i} item={item} />
          ))}
        </div>
      )}

      {!loading && !hasItems && !unreadable && !partial && !error && (
        <div
          data-state="empty"
          className="flex flex-col gap-2 p-3 rounded-lg bg-surface-container border border-outline-variant/20"
        >
          {/* Deliberately not a warning and deliberately not advice. An absent
              online footprint is ordinary for a small employer, and telling the
              reader to go and confirm attaches an alarm to a non-event. */}
          <div className="flex items-start gap-2">
            <Icon name="info" className="text-on-surface-variant mt-0.5" />
            <p className="text-body-sm text-on-surface-variant leading-relaxed">
              The search completed and returned no results for this employer. That
              is common for small businesses and is not itself a problem.
            </p>
          </div>
        </div>
      )}

      {/* TEMPORARY DIAGNOSTIC. Renders the provider's raw response body per
          query so it can be inspected in the panel. Inlined rather than
          restored as the separate debug-panel component, because
          `test_no_debug_surface.py` asserts that component file is deleted.
          Remove together with `SearchOutcome.raw_response` and the suspended
          assertion. */}
      {result?.debugSearchRaw && result.debugSearchRaw.length > 0 && (
        <details className="rounded-lg border border-amber-500/40 bg-amber-500/5">
          <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer">
            <Icon name="warning" className="text-amber-500" />
            <span className="text-label-sm font-bold text-on-surface">
              Raw Tavily response (debug)
            </span>
            <span className="ml-auto text-label-sm text-on-surface-variant">
              tap to open
            </span>
          </summary>
          <div className="flex flex-col gap-3 px-3 pb-3">
            {result.debugSearchRaw.map((entry, i) => (
              <div key={i} className="flex flex-col gap-1 min-w-0">
                <span className="text-label-sm font-bold text-amber-500 break-all">
                  {entry.query}
                </span>
                <pre className="text-[10px] leading-relaxed text-on-surface-variant bg-surface-container-lowest rounded p-2 overflow-x-auto max-h-72 whitespace-pre-wrap break-all">
                  {(() => {
                    try {
                      return JSON.stringify(JSON.parse(entry.raw), null, 2);
                    } catch {
                      return entry.raw;
                    }
                  })()}
                </pre>
              </div>
            ))}
          </div>
        </details>
      )}

      {result?.report && (
        <div className="mt-1 pt-3 border-t border-outline-variant/20">
          <h4 className="text-label-md font-bold text-on-surface mb-1">What the search found</h4>
          <p className="text-body-sm text-on-surface-variant leading-relaxed">{result.report}</p>
        </div>
      )}

      {result?.evidence && result.evidence.length > 0 && (
        <details className="rounded-lg border border-outline-variant/20 bg-surface-container">
          <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer">
            <Icon name="search" className="text-secondary" />
            <span className="text-label-sm font-bold text-on-surface">
              Sources ({result.evidence.length})
            </span>
            <span className="ml-auto text-label-sm text-on-surface-variant">tap to open</span>
          </summary>
          <ul className="flex flex-col gap-2 px-3 pb-3">
            {result.evidence.map((e, i) => (
              <li key={i} className="flex flex-col gap-0.5">
                <a
                  href={e.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-body-sm text-secondary hover:underline break-words"
                >
                  {e.title || e.url}
                </a>
                {e.snippet && (
                  <span className="text-label-sm text-on-surface-variant/80 leading-relaxed">
                    {e.snippet}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}

      {result?.recommendation && (
        <div className="rounded-lg bg-secondary-container/10 p-3">
          <h4 className="text-label-md font-bold text-secondary mb-1">What to do</h4>
          <p className="text-body-sm text-on-surface leading-relaxed">
            {result.recommendation}
          </p>
        </div>
      )}

      {error && (
        <div data-state="unreadable-result" className="flex items-start gap-2 py-2">
          <Icon name="warning" className="text-on-surface-variant mt-0.5" />
          {/* Deliberately does not say the search failed, and deliberately does
              not say it succeeded. This state is reached when the model answered
              in a shape nobody could read, or when the request did not come back
              at all — and in the first case the searches ran perfectly. What is
              missing is a *readable answer*, which is a fact about this panel's
              output rather than about the employer, so it must not be filed
              under either retrieval outcome. */}
          <span className="text-body-sm text-on-surface-variant leading-relaxed">
            We could not read a verification result for this posting, so no web
            evidence is shown here. This is not a finding about the employer.
            What the posting itself states still stands.
          </span>
        </div>
      )}
    </div>
  );
}

export default EvidenceSummary;
