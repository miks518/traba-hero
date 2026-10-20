import React from 'react';
import { Icon } from '../common';
import type { Anomaly, AnomalyAssessment, IconName } from '../../types';

export interface AnomalyCardsProps {
  anomalies: Anomaly[];
  /**
   * The employer lookup is still running. Read `result.verificationLoading`
   * directly, never the sticky `verificationFailed` flag: a failed lookup must
   * stop the spinner, not keep it forever.
   */
  checking?: boolean;
  /** The posting named no employer, so nothing could be searched. */
  needsCompanyName?: boolean;
  /** The employer search did not finish. */
  verificationError?: boolean;
  /**
   * Whether the verify response carried `anomaly_assessments` at all. `false`
   * means the reading predates the check; it never means the findings were
   * stale.
   */
  assessmentRun?: boolean;
}

type DisplayState = 'checking' | 'stale' | 'low' | 'mid' | 'high' | 'unconfirmed';

const CHIP: Record<DisplayState, { cls: string; label: string; icon: IconName }> = {
  checking: {
    cls: 'border border-outline-variant/40 text-on-surface-variant',
    label: 'Checking',
    icon: 'search',
  },
  // Grey, not green. The finding is retired, not a clean employer record.
  stale: { cls: 'chip-stale', label: 'Stale', icon: 'check_circle' },
  high: { cls: 'chip-critical', label: 'Critical', icon: 'warning' },
  mid: { cls: 'chip-caution', label: 'Serious', icon: 'warning' },
  low: { cls: 'chip-verified', label: 'Minor', icon: 'warning' },
  unconfirmed: { cls: 'chip-caution', label: 'Unconfirmed', icon: 'question_mark' },
};

const STRIP: Record<
  AnomalyAssessment['status'],
  { cls: string; label: string; icon: IconName; iconCls: string }
> = {
  stale: {
    cls: 'status-card-stale',
    label: 'No longer a concern',
    icon: 'check_circle',
    iconCls: 'text-on-surface-variant',
  },
  red: {
    cls: 'status-card-critical',
    label: 'Contradicted by a public source',
    icon: 'gpp_bad',
    iconCls: 'text-error',
  },
  yellow: {
    cls: 'status-card-caution',
    label: 'Not confirmed',
    icon: 'gpp_maybe',
    iconCls: 'text-verdict-caution',
  },
};

/**
 * The card's display state.
 *
 * The scan's severity is input, not the answer. A finding the evidence
 * accounts for is `stale` (grey) whatever the scan weighed it at; a finding
 * the evidence contradicts keeps the scan's severity; anything unresolved is
 * amber `Unconfirmed`. `Checking` is its own state and carries no severity.
 */
function displayState(
  anomaly: Anomaly,
  checking: boolean,
  assessment: AnomalyAssessment | null,
): DisplayState {
  if (checking) return 'checking';
  if (!assessment) return 'unconfirmed';
  if (assessment.status === 'stale') return 'stale';
  if (assessment.status === 'red') return anomaly.severity ?? 'mid';
  return 'unconfirmed';
}

/**
 * The assessment to show, or the honest reason there is none.
 *
 * A failed lookup and a missing employer override an assessment left over from
 * an earlier run: the current reading did not complete, and the card says so
 * rather than presenting the previous verdict as current.
 */
function resolvedAssessment(
  anomaly: Anomaly,
  props: Pick<AnomalyCardsProps, 'checking' | 'needsCompanyName' | 'verificationError' | 'assessmentRun'>,
): AnomalyAssessment | null {
  if (props.checking) return null;
  if (props.needsCompanyName) {
    return {
      status: 'yellow',
      finding: 'This post names no employer, so there was nothing to search. Shown so you notice it.',
    };
  }
  if (props.verificationError) {
    return {
      status: 'yellow',
      finding: 'The employer search did not finish, so this finding was not checked.',
    };
  }
  if (anomaly.assessment) {
    const assessment = anomaly.assessment;
    // The backend demotes an unbacked `stale`/`red` already. Repeating the rule
    // here is not belt-and-braces: a saved scan, a hand-edited response, or a
    // future caller can all reach the card without passing through that parser,
    // and a retired finding shown without its source is the one state this
    // component must never render.
    if (assessment.status !== 'yellow' && !assessment.sourceUrl) {
      return {
        status: 'yellow',
        finding: 'No public source was recorded for this finding, so it was not confirmed.',
      };
    }
    return assessment;
  }
  if (props.assessmentRun) {
    return {
      status: 'yellow',
      finding: 'No evidence verdict was recorded for this finding.',
    };
  }
  return {
    status: 'yellow',
    finding: 'This reading has no evidence verdict. It may have been saved before findings were checked.',
  };
}

/**
 * The findings, one card each.
 *
 * **The card is present from the moment the scan lands.** The finding is what
 * the scan detected; verification cannot un-detect it. While the lookup runs
 * the chip is neutral `Checking` and the evidence strip is a spinner, so no
 * severity is asserted before the evidence is in.
 *
 * **The final chip follows the evidence, not a second model judgement.**
 * `stale → Stale` (grey), `red → the scan's severity`, `yellow → Unconfirmed`,
 * waiting → `Checking`. The mapping is derived here, so the chip cannot
 * disagree with the strip above it.
 *
 * **Grey is not green.** A stale finding is retired, not a clean record for the
 * employer. The six category checks still use green for a confirmed claim; this
 * card deliberately does not.
 *
 * **No finding is silently dropped.** A finding that is missing a verdict, that
 * was too numerous to check, or that belongs to a failed lookup stays on screen
 * with an amber note saying which.
 *
 * The rule code and the posting's own words are unchanged: `code` is the
 * taxonomy ID when the scan carried one, and `quote` is the screened span the
 * finding was drawn from. An absent value degrades the card rather than being
 * filled with a guess.
 */
export function AnomalyCards({
  anomalies,
  checking = false,
  needsCompanyName = false,
  verificationError = false,
  assessmentRun = false,
}: AnomalyCardsProps) {
  if (anomalies.length === 0) return null;

  return (
    <section className="flex flex-col gap-3" data-role="anomaly-cards">
      <div className="flex items-center justify-between gap-2 px-1">
        <h3 className="text-headline-sm font-headline font-bold text-on-surface">Anomalies detected</h3>
        {/* min-w-0 on the heading side so one long word cannot push the count out
            of a narrow panel. The count is the figure Phase 6.3 measures, so it
            has to survive the layout rather than being the first thing dropped. */}
        <span className="text-body-sm font-semibold text-on-surface-variant shrink-0">
          {anomalies.length} found
        </span>
      </div>

      {anomalies.map((anomaly) => {
        const assessment = resolvedAssessment(anomaly, {
          checking,
          needsCompanyName,
          verificationError,
          assessmentRun,
        });
        const state = displayState(anomaly, checking, assessment);
        const chip = CHIP[state];
        const strip = assessment ? STRIP[assessment.status] : null;

        return (
          <article
            key={anomaly.id}
            data-role="anomaly-card"
            data-state={state}
            className="tactile-card bg-surface-container-lowest border border-outline-variant/20 rounded-lg p-4 flex flex-col gap-2.5"
          >
            <div className="flex items-center justify-between gap-2">
              <span
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold ${chip.cls}`}
              >
                <Icon name={chip.icon} className="text-[11px] leading-none" />
                {chip.label}
              </span>

              {/*
                The rule code, when the scan carried one.

                Absent for a scan taken before the field existed, and that is a
                different state from `OTHER` — `OTHER` means the model answered
                the escape valve deliberately, and it is shown, because the
                frequency of escape-valve answers is the drift signal the
                taxonomy exists to produce. An absent code is a scan from before
                the taxonomy and gets no pill at all.
              */}
              {anomaly.code && (
                <span className="code-pill px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase shrink-0">
                  {anomaly.code}
                </span>
              )}
            </div>

            <div className="flex flex-col gap-1 min-w-0">
              <h4 className="text-headline-xs font-headline font-bold text-on-surface break-words">
                {anomaly.title}
              </h4>
              <p className="text-body-sm text-on-surface-variant leading-normal break-words">
                {anomaly.description}
              </p>
            </div>

            {/*
              The posting's own words, in a recessed well.

              This is the most load-bearing thing on the card: a finding a reader
              cannot check against the posting is a claim, and a claim about a
              named employer is the exact exposure this product's prompt rules
              exist to prevent. Showing the span that decided it is what makes the
              finding checkable.
            */}
            {anomaly.quote && (
              <div className="quote-well p-3 flex flex-col gap-1">
                <span className="text-[10px] font-bold text-on-surface-variant tracking-wider uppercase">
                  From the post
                </span>
                <p className="text-body-sm text-on-surface leading-relaxed break-words">
                  {anomaly.quote}
                </p>
              </div>
            )}

            {state === 'checking' ? (
              <div
                role="status"
                aria-busy="true"
                className="rounded-md border border-outline-variant/30 bg-surface-container-low p-3 flex items-start gap-2.5"
              >
                <span
                  aria-hidden="true"
                  className="mt-0.5 w-4 h-4 shrink-0 rounded-full border-2 border-outline-variant border-t-transparent animate-spin"
                />
                <span className="text-body-sm text-on-surface-variant leading-snug">
                  Confirming this finding against public sources…
                </span>
              </div>
            ) : (
              strip && assessment && (
                <div
                  className={`${strip.cls} border rounded-md p-3 flex flex-col gap-1`}
                  data-role="anomaly-evidence"
                  data-status={assessment.status}
                >
                  <div className="flex items-center gap-1.5">
                    <Icon name={strip.icon} className={`text-sm leading-none ${strip.iconCls}`} />
                    <span className="text-[10px] font-bold text-on-surface-variant tracking-wider uppercase">
                      {strip.label}
                    </span>
                  </div>
                  {assessment.finding && (
                    <p className="text-body-sm text-on-surface leading-relaxed break-words">
                      {assessment.finding}
                    </p>
                  )}
                  {assessment.sourceUrl && (
                    <a
                      href={assessment.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      data-role="anomaly-source"
                      className="inline-flex items-center gap-1 text-body-sm font-semibold text-on-surface underline underline-offset-2 hover:text-on-surface-variant break-all"
                    >
                      <Icon name="open_in_new" className="text-sm leading-none shrink-0" />
                      {assessment.sourceTitle || assessment.sourceUrl}
                    </a>
                  )}
                </div>
              )
            )}
          </article>
        );
      })}
    </section>
  );
}

export default AnomalyCards;
