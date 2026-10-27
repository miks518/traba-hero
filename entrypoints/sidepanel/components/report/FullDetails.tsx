import React, { useId, useState } from 'react';
import { Icon } from '../common';
import { shouldShowCheck } from '../../lib/riskDisplay';
import { groupBy, statusPresentation } from './checkPresentation';
import type { VerificationItem, VerificationResult } from '../../types';
import type { AssessmentTone } from './assessmentCopy';

export interface FullDetailsProps {
  result?: VerificationResult;
  /**
   * The assessment tone to fill this disclosure with, so it matches the banner
   * above it rather than reading as a foreign card.
   *
   * Supplied by `ReportPanel` rather than looked up here: the banner's tone is
   * decided once, from the level and the verifying flag, and asking two
   * components to reach the same answer is how they stop agreeing.
   *
   * `unknown` while verification is in flight — the same reason the banner uses
   * it. The posting stage has a level, but the settled one can still move, and a
   * red-toned disclosure over a result that is about to come back clean is the
   * same overclaim as the retired score, in a new place.
   */
  tone?: AssessmentTone;
}

/**
 * The retrieval half, behind a disclosure — slot 8.
 *
 * Split from `WhatWeChecked` because the two answer different questions and carry
 * **opposite honesty requirements.** `WhatWeChecked` asserts that checks were
 * performed, so a line there that cannot be backed by a real check is a false
 * claim about coverage. This one just shows what retrieval returned, which is
 * safe to show whether or not it amounts to anything. Collapsing them back into
 * one component would mean choosing which of those two rules to obey.
 *
 * **This is where a check's explanation is shown, and that was a hole.** Every
 * `VerificationItem` carries an `explanation` — the model's account of what
 * decided its status — and until now it was parsed, bound to a retrieved URL,
 * weighed by `risk_calculator`, serialised onto the wire, typed on the client,
 * and then never rendered. The panel showed the word "Channel Match" in a red
 * bucket and no sentence anywhere on screen, which is a panel that asserts a
 * contradiction exists while withholding the only account of what contradicts
 * what. A reader cannot act on a finding they cannot read.
 *
 * So the groups from `WhatWeChecked` are repeated here with the sentences
 * attached, sharing `groupBy` and `statusPresentation` rather than restating
 * them. The repetition is the correlation: a label above matches its sentence
 * below, and the grouping is what makes that pairing legible.
 *
 * **The share filter is not optional here.** `shouldShowCheck` hides an `unknown`
 * Reputation, and its docstring says why: that finding used to read "The search
 * results do not contain any scam reports, fraud warnings, formal complaints…",
 * putting the words *scam* and *fraud* beside a named company in order to report
 * nothing. That was the panel's only surface for model-written per-check prose,
 * so the exposure was bounded to one label. Rendering the sentences makes this
 * the surface where a model's words about a named employer are actually shown —
 * so the same filter runs here, or the guardrail that everything else obeys has
 * exactly one hole in it.
 *
 * **The disclosure's own copy does not promise retrieval times.** The design
 * promises "every finding with its source link and *retrieval time*", and nothing
 * records a retrieval time — search results carry a score and content, not a
 * timestamp. A disclosure that overstates its own contents is worse than no
 * disclosure, so the promise is dropped rather than the field faked.
 *
 * **Everything inside is a container, and each check group is one tinted by its
 * status.** The three blocks — the checks, the report prose, the sources — each sit
 * in a card, inside one flat parent. Within the checks, each of the three groups
 * (Verified, Contradicted, Could not verify) is its own card filled with that
 * status's chip tint, so the three read apart by shape and colour before a word is
 * read, and a red finding is visible as a colour rather than only as a label.
 *
 * Before this they were bare text on the panel background, separated only by
 * `gap-4`, and a reader opening the disclosure could not tell where the check
 * findings ended and the search report began. That is the specific harm: the blocks
 * looked like one undifferentiated run, so the reader cannot tell a *finding* from a
 * *summary* from a *source*, which is the distinction the whole component is split
 * on. See `BODY_CLASS` for why the two enclosing containers carry no shadow.
 */

/**
 * The checks worth showing a sentence for.
 *
 * Two filters, in this order and both load-bearing:
 *
 *   1. `shouldShowCheck` — the shared libel guardrail, described above. It is
 *      imported rather than reimplemented so this cannot become a second policy.
 *   2. a non-empty `explanation` — a `yellow` check whose finding was left blank
 *      by the prompt has nothing to disclose. Rendering the label with an empty
 *      paragraph under it would be a placeholder, and the panel's standing rule
 *      is that an absent thing is not dressed as a present one.
 */
function explainedChecks(result?: VerificationResult): VerificationItem[] {
  return (result?.items ?? [])
    .filter(shouldShowCheck)
    .filter((item) => item.explanation.trim().length > 0);
}

/**
 * The three blocks inside the disclosure share one card treatment.
 *
 * **`px-1` is gone from the block headings.** They used to sit directly on the
 * panel background, level with the "Full details and sources" header above them,
 * so a heading and the header it belongs to were indented identically and the
 * three blocks ran together as one undifferentiated column. Indentation was doing
 * the work of separation, which is the one thing it cannot do well at this size —
 * and it meant nothing separated the last source from the report paragraph above
 * it.
 *
 * One step for all three, not one per block. The five `surface-container` steps
 * are a depth scale, not a palette: `lowest` is the panel's own card fill, and
 * stepping between them would encode a difference that does not exist between
 * "what each check found", "what the search found" and "sources". Status colour is
 * already carried by the Verified / Contradicted / Could-not-verify chips, and
 * duplicating it in the fill would put a second, quieter claim on the same fact.
 */
const BLOCK_CLASS =
  'tactile-card bg-surface-container-lowest border border-outline-variant/20 rounded-lg p-4';

/**
 * The parent. A fill and a border, **deliberately no `tactile-card`**.
 *
 * It contains three containers that each already carry a hard shadow. Stacking
 * four extrusions — one around the group, three around its children — reads as
 * noise and spends the elevation cue on nothing, since the design record holds
 * that the shadow is what tells a reader an element is a distinct surface. The one
 * shadow belongs to the things inside it.
 */
const BODY_CLASS = 'mt-3 bg-surface-container-low border border-outline-variant/20 rounded-lg p-3';

/**
 * The wrapper around the three status-tinted group cards.
 *
 * Flat, for the same reason `BODY_CLASS` is, and the rule is the same one applied
 * consistently: **a container that holds containers is not itself a card.** The
 * three groups carry the shadows; a fourth extrusion around them would put a
 * `tactile-card` inside a `tactile-card`, which is the nesting this component
 * has now been un-nested from twice.
 *
 * It keeps the neutral fill and the border so it still reads as the block that
 * holds the checks, distinct from the report prose and the sources beside it.
 */
const WRAPPER_CLASS = 'bg-surface-container-low border border-outline-variant/20 rounded-lg p-3';

/** One check: its label, what decided it, and the result it came from. */
function CheckDetail({ item }: { item: VerificationItem }) {
  const mark = statusPresentation(item.status);
  return (
    <li className="flex items-start gap-2.5 min-w-0" data-role="check-detail" data-status={item.status}>
      <Icon name={mark.icon} filled className={`${mark.cls} text-lg leading-none mt-0.5 shrink-0`} aria-hidden />
      <div className="flex flex-col gap-1 min-w-0">
        <p className="text-body-sm font-bold text-on-surface leading-snug break-words">{item.label}</p>
        <p className="text-body-sm text-on-surface-variant leading-relaxed break-words">{item.explanation}</p>
        {item.source_url && (
          <a
            href={item.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-label-sm text-secondary hover:underline break-words inline-flex items-start gap-1 self-start"
          >
            <Icon name="open_in_new" className="text-[11px] mt-0.5 shrink-0" />
            <span className="min-w-0">{item.source_title || item.source_url}</span>
          </a>
        )}
      </div>
    </li>
  );
}

/** The checks, under the same three headings the summary above uses. */
function CheckDetails({ items }: { items: VerificationItem[] }) {
  const groups = groupBy(items).filter((g) => g.items.length > 0);
  if (groups.length === 0) return null;

  return (
    <section className={`${WRAPPER_CLASS} flex flex-col gap-3`} data-role="check-details">
      <h4 className="text-label-md font-bold text-on-surface">What each check found</h4>
      {groups.map((group) => (
        /*
          One card per group, tinted by the state the group carries — contradicted
          red, confirmed and supported green, could-not-verify amber — so a reader
          can tell them apart without reading the headings, and so a contradicted
          finding is visible as a shape rather than only as a word.

          The chip keeps its saturated text and drops its own fill
          (`chip-cutout`), because a chip-coloured chip on a chip-coloured card
          is invisible. It is the cut-out that carries the label; the card behind
          it carries the status.
        */
        <section
          key={group.key}
          className={`tactile-card ${group.tint} border rounded-lg p-4 flex flex-col gap-3`}
          data-group={group.key}
        >
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold shrink-0 ${group.chip} chip-cutout`}
            >
              <Icon name={group.icon} filled className="text-[13px] leading-none" />
              {group.label}
            </span>
            <div className="h-px bg-outline-variant/20 flex-1" />
          </div>
          <ul className="flex flex-col gap-3">
            {group.items.map((item, i) => (
              <CheckDetail key={`${group.key}-${i}`} item={item} />
            ))}
          </ul>
        </section>
      ))}
    </section>
  );
}

export function FullDetails({ result, tone = 'unknown' }: FullDetailsProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  const evidence = result?.evidence ?? [];
  const hasEvidence = evidence.length > 0;
  const checks = explainedChecks(result);
  const hasChecks = checks.length > 0;

  // Nothing behind the disclosure, so nothing to disclose. An empty disclosure
  // titled "Full details and sources" over an empty column asserts that detail
  // was withheld, which is a different claim from there being none.
  //
  // The checks are counted alongside the prose and the sources because they are
  // now the other thing behind it. Leaving them out is the case that matters: a
  // `red` whose citation `_bind_to_retrieved` stripped arrives with no source and
  // no evidence list, and an early return keyed on the old two conditions would
  // hide the disclosure holding the only sentence explaining the contradiction.
  if (!hasEvidence && !result?.report && !hasChecks) return null;

  return (
    <section data-role="full-details" data-disclosure data-open={open ? 'true' : 'false'}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className={`tactile-disclosure tactile-assessment-${tone} w-full px-4 py-3 flex items-center justify-between gap-2 text-left cursor-pointer`}
        data-role="full-details-toggle"
      >
        <span className="text-body-md font-headline font-semibold min-w-0">
          Full details and sources
        </span>
        <Icon name="keyboard_arrow_down" className="disclosure-chevron shrink-0" />
      </button>

      {open && (
        <div id={panelId} className={BODY_CLASS} data-role="full-details-body">
          <div className="flex flex-col gap-3">
            <CheckDetails items={checks} />

            {result?.report && (
              <section className={`${BLOCK_CLASS} flex flex-col gap-1`} data-role="search-report">
                <h4 className="text-label-md font-bold text-on-surface">What the search found</h4>
                <p className="text-body-sm text-on-surface-variant leading-relaxed">{result.report}</p>
              </section>
            )}

            {/* The evidence list had no heading of its own, so it ran straight
                into the block above it with nothing to mark where it began. A
                heading that names the block is also the honest description of it:
                these are the results retrieval returned, not findings, which is
                the same distinction the component is split on. */}
            {hasEvidence && (
              <section className={`${BLOCK_CLASS} flex flex-col gap-2.5`} data-role="search-evidence">
                <h4 className="text-label-md font-bold text-on-surface">Sources</h4>
                <ul className="flex flex-col gap-2.5">
                  {evidence.map((e, i) => (
                    <li key={i} className="flex flex-col gap-0.5 min-w-0">
                      <a
                        href={e.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-body-sm text-secondary hover:underline break-words inline-flex items-start gap-1"
                      >
                        <Icon name="open_in_new" className="text-[11px] mt-1 shrink-0" />
                        <span className="min-w-0">{e.title || e.url}</span>
                      </a>
                      {e.snippet && (
                        <span className="text-label-sm text-on-surface-variant leading-relaxed pl-5">
                          {e.snippet}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

export default FullDetails;