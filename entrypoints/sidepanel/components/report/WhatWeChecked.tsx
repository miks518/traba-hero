import React from 'react';
import { Icon } from '../common';
import { shouldShowCheck } from '../../lib/riskDisplay';
import { groupBy, statusPresentation } from './checkPresentation';
import type { VerificationResult } from '../../types';

export interface WhatWeCheckedProps {
  result?: VerificationResult;
  loading?: boolean;
  error?: boolean;
  /** The search currently running, shown while the lookup is in flight. */
  currentQuery?: string;
}

/**
 * The check half of the old `EvidenceSummary`, split out per architecture §7.
 *
 * This section asserts that **checks were performed**. That is the opposite
 * requirement from `FullDetails`, which shows what retrieval returned, and it is
 * why the two cannot be one component: a line here that cannot be backed by a
 * real check is a false claim about coverage wearing the honest hat. So every
 * rule below is about not claiming a check that did not happen.
 *
 * **Four groups, not two.** The design splits into *Verified* and *Could not
 * verify*. That leaves the `contradicted` items with nowhere to go, and a
 * contradicted claim is not a failed check — it is the check *succeeding* and
 * finding the opposite of what the posting stated. Folding it into "could not
 * verify" would lose the single most important thing verification can produce;
 * folding it into "confirmed" would be the flatly opposite lie.
 *
 * `confirmed` and `supported` are separate groups for the same reason: calling a
 * record that was never compared against the posting's channel *confirmed* would
 * be that lie in a smaller place.
 *
 * **No coverage count.** The design puts "13 of 14 done" in the header and calls
 * it a first-class figure. The denominator is the problem: it must be a constant
 * the backend owns, because a number written into the panel drifts with whatever
 * the panel happens to render, and that is how a "14 checks" claim quietly
 * becomes 6. No backend constant exists yet, so rather than counting what this
 * component drew — which is exactly the lie — the count is absent.
 *
 * **Labels only. The sentences live in `FullDetails`.** Every check carries an
 * `explanation` — the model's own account of what decided its status — and it is
 * deliberately not rendered here. This section's contract is that checks were
 * performed, and a paragraph of model-written prose under a heading that asserts
 * coverage is a different claim at a different weight: it reads as a finding
 * sitting in the summary, and it crowds a column sized for two-word labels. The
 * same checks appear with their explanations one disclosure away, filed by the
 * shared grouping rather than a second copy of it, so a label above matches its
 * sentence below.
 *
 * **No per-line failure reason.** The design shows "The careers page did not
 * load" under a could-not-verify line. Those are *retrieval-level* facts and the
 * only channel for them today is the top-level `searchOk` / `searchPartial` /
 * `searchError` triple, which describes the search as a whole and cannot say
 * which category was thin. The lines therefore carry only what they can support.
 */

/**
 * The heading, derived from what actually happened.
 *
 * "What we checked" is only true when checks ran. The three other outcomes are
 * not summaries of checks — a lookup still running, one that could not complete,
 * and one that ran and returned nothing are three different facts about *our*
 * retrieval, and each is named rather than filed under checks. This logic is
 * carried over intact from `EvidenceSummary`, whose heading was derived for the
 * same reason, and it is not re-litigated here.
 */
function headingFor(state: {
  loading: boolean;
  hasItems: boolean;
  unreadable: boolean;
  partial: boolean;
  error: boolean;
}): string {
  if (state.loading && !state.hasItems) return 'Checking this company';
  if (state.error) return 'Verification could not be completed';
  if (state.unreadable) return 'The search could not run';
  if (state.hasItems) return 'What we checked';
  if (state.partial) return 'Partial search coverage';
  return 'Searched, found nothing';
}

export function WhatWeChecked({
  result,
  loading,
  error,
  currentQuery,
}: WhatWeCheckedProps) {
  // Derived from what will actually render, not from the raw list. Hiding a
  // check must not leave a "What we checked" heading sitting over an empty
  // column, which asserts checks were summarised when none were.
  const visibleItems = (result?.items ?? []).filter(shouldShowCheck);
  const hasItems = visibleItems.length > 0;
  const unreadable = result?.searchOk === false;
  const partial = Boolean(result?.searchPartial);
  // `searchOk: false` and `error` can arrive together: the searches may have
  // completed and the model's answer then failed to parse, which is not the
  // search's failure and must not be described as one.
  const unreadableAnswer = Boolean(error) && unreadable;

  const heading = headingFor({ loading: Boolean(loading), hasItems, unreadable, partial, error: Boolean(error) });
  const groups = groupBy(visibleItems).filter((g) => g.items.length > 0);

  return (
    <section className="flex flex-col gap-3" data-role="what-we-checked">
      <div className="flex items-center justify-between gap-2 px-1">
        <h3 className="text-headline-sm font-headline font-bold text-on-surface">{heading}</h3>
        {loading && (
          <span className="inline-flex items-center gap-1.5 text-body-sm text-on-surface-variant shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-ping" />
            Searching
          </span>
        )}
      </div>

      {loading && !hasItems && (
        <div className="tactile-card bg-surface-container-lowest border border-outline-variant/20 rounded-lg p-4 flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-full border-2 border-secondary border-t-transparent animate-spin" />
          {currentQuery && (
            <span className="text-label-sm text-on-surface-variant max-w-full truncate text-center">
              {currentQuery}
            </span>
          )}
        </div>
      )}

      {/* A lookup that could not complete reports that, and lists no checks. The
          absence is the content: rendering an empty "What we checked" under a
          populated heading would claim we looked when we did not. */}
      {unreadable && (
        <div
          data-state="unreadable"
          className="tactile-card bg-surface-container-lowest border border-outline-variant/20 rounded-lg p-4 flex items-start gap-2"
        >
          <Icon name="warning" className="text-error mt-0.5 shrink-0" />
          <p className="text-body-sm text-on-surface-variant leading-relaxed min-w-0">
            {unreadableAnswer
              ? 'The answer could not be read, so nothing about this employer was established. Whether the searches ran is not recorded here. This is not a finding about them. What the posting itself says still stands.'
              : 'The web search did not run, so nothing about this employer is known. This is not a finding about them. What the posting itself says still stands.'}
          </p>
        </div>
      )}

      {partial && (
        <div
          data-state="partial"
          className="tactile-card bg-surface-container-lowest border border-outline-variant/20 rounded-lg p-4 flex items-start gap-2"
        >
          <Icon name="warning" className="text-verdict-caution mt-0.5 shrink-0" />
          <p className="text-body-sm text-on-surface-variant leading-relaxed min-w-0">
            {result?.queriesFailed && result?.queriesIssued
              ? `${result.queriesFailed} of ${result.queriesIssued} searches failed, `
              : 'One of the searches failed, '}
            so some checks were made against a thinner set of results than the others.
            This is not a finding about the employer, and an unconfirmed claim may
            simply not have been covered.
          </p>
        </div>
      )}

      {hasItems && (
        <div className="tactile-card bg-surface-container-lowest border border-outline-variant/20 rounded-lg p-4 flex flex-col gap-4">
          {groups.map((group) => (
            <div key={group.key} className="flex flex-col gap-2.5" data-group={group.key}>
              <div className="flex items-center gap-2.5">
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold shrink-0 ${group.chip}`}
                >
                  <Icon name={group.icon} filled className="text-[13px] leading-none" />
                  {group.label}
                </span>
                <div className="h-px bg-outline-variant/20 flex-1" />
              </div>

              {group.items.map((item, i) => {
                // Read the icon and its colour from the item's own status rather
                // than from the group it happens to be filed under. The two agree
                // today; deriving both from one place is what stops them drifting
                // apart if a fourth status ever appears.
                const mark = statusPresentation(item.status);
                return (
                  <div key={`${group.key}-${i}`} className="flex items-start gap-2.5 pl-0.5">
                    <Icon
                      name={mark.icon}
                      filled
                      className={`text-lg leading-none mt-px shrink-0 ${mark.cls}`}
                      aria-hidden
                    />
                    <p className="text-body-sm text-on-surface leading-snug min-w-0 break-words">
                      {item.label}
                    </p>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}

      {/* A search that ran and found nothing is not a warning and not advice. An
          absent online footprint is ordinary for a small employer, and telling the
          reader to go and confirm attaches an alarm to a non-event. */}
      {!loading && !hasItems && !unreadable && !partial && !error && (
        <div
          data-state="empty"
          className="tactile-card bg-surface-container-lowest border border-outline-variant/20 rounded-lg p-4 flex items-start gap-2"
        >
          <Icon name="info" className="text-on-surface-variant mt-0.5 shrink-0" />
          <p className="text-body-sm text-on-surface-variant leading-relaxed min-w-0">
            The search completed and returned no results for this employer. That is
            common for small businesses and is not itself a problem.
          </p>
        </div>
      )}

      {/* Deliberately says neither that the search failed nor that it succeeded.
          This state is reached when the model answered in a shape nobody could
          read, or when the request did not come back at all — and in the first
          case the searches ran perfectly. What is missing is a *readable answer*,
          which is a fact about this panel's output rather than about the
          employer, so it must not be filed under either retrieval outcome. */}
      {error && !unreadable && (
        <div data-state="unreadable-result" className="flex items-start gap-2 px-1">
          <Icon name="warning" className="text-on-surface-variant mt-0.5 shrink-0" />
          <span className="text-body-sm text-on-surface-variant leading-relaxed">
            We could not read a verification result for this posting, so no web
            evidence is shown here. This is not a finding about the employer. What
            the posting itself states still stands.
          </span>
        </div>
      )}

      {/*
        TEMPORARY DIAGNOSTIC, relocated not removed.

        This was the `debugSearchRaw` block inside `EvidenceSummary.tsx`. That
        component was deleted with the report panel and the block went with it,
        which was wrong: `backend/tests/test_no_debug_surface.py` carries a
        deliberate skip naming this block as a diagnostic that is *in use*, and
        `SearchOutcome.raw_response` is still emitted by the backend and still
        mapped onto `VerificationResult.debugSearchRaw` in `lib/api.ts`. Silently
        dropping the renderer would have left the wire carrying a field nothing
        displays, and taken with it the ability to see what Tavily actually
        returns — which is exactly what is needed while the parser is still
        mis-shaping responses.

        Remove this together with `SearchOutcome.raw_response` from
        `app/services/search.py`, the `debug_search_raw` field in
        `verification_flow.py`, and then the skip in that test.
      */}
      {result?.debugSearchRaw && result.debugSearchRaw.length > 0 && (
        <details className="rounded-lg border border-verdict-caution/40 bg-chip-caution-bg">
          <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer">
            <Icon name="warning" className="text-verdict-caution" />
            <span className="text-label-sm font-bold text-on-surface">
              Raw Tavily response (debug)
            </span>
            <span className="ml-auto text-label-sm text-on-surface-variant">tap to open</span>
          </summary>
          <div className="flex flex-col gap-3 px-3 pb-3">
            {result.debugSearchRaw.map((entry, i) => (
              <div key={i} className="flex flex-col gap-1 min-w-0">
                <span className="text-label-sm font-bold text-verdict-caution break-all">
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
    </section>
  );
}

export default WhatWeChecked;
