import type { IconName } from '../common';
import type { VerificationItem } from '../../types';

/**
 * How one verification check is grouped and marked, in both places it appears.
 *
 * **Extracted because a check is now shown twice, and the two renderings have to
 * agree.** `WhatWeChecked` shows the label alone, in a bucketed column;
 * `FullDetails` shows the same checks with the model's sentence under each one.
 * The reader correlates them by eye — the words *Channel Match* in a bucket
 * above are matched to the paragraph explaining them below — and that
 * correlation is the entire point. Two copies of the grouping would let a state
 * read confirmed above and be filed under "Could not verify" below, which is
 * worse than not showing the sentence at all.
 *
 * Nothing here decides *which* checks are visible. That is `shouldShowCheck` in
 * `lib/riskDisplay`, shared by both components for the same reason; this module
 * only says how a check already admitted is marked.
 *
 * **One vocabulary, four states.** The panel used to carry two incompatible
 * status systems — `green`/`yellow`/`red` for the six claim categories and
 * `stale`/`yellow`/`red` for the findings — and a model-written status beside a
 * code-owned one is two assessments in one panel. They disagree, and the corpus
 * caught one: a red Location/Branch card on a 600-store franchise, because the
 * company's own page listed a different venue. Both vocabularies now retire
 * onto the establishment states:
 *
 *   confirmed     the comparison was made and it matched
 *   supported     an independent record names the employer, but the posting's
 *                 channel was not compared against it
 *   contradicted  a retrieved source shows the claim is not the employer's
 *   unknown       the lookup found nothing, or nothing bearing on identity
 *
 * `confirmed` and `supported` are kept apart rather than pooled under one
 * "Verified" heading, because calling a record that was never compared
 * *confirmed* is the overclaim a single heading would make.
 */
export type CheckState = 'confirmed' | 'supported' | 'contradicted' | 'unknown';

export interface Group {
  key: CheckState;
  label: string;
  chip: string;
  /**
   * The tint for a card holding this whole group.
   *
   * Separate from `chip` because the chip is a saturated-on-pale label and the
   * card is the pale fill itself — two different jobs, one status. `FullDetails`
   * renders the group as a card and keeps the chip inside it, cut out against
   * `chip-cutout`, so the status is legible in both without the chip vanishing
   * into the fill it shares.
   */
  tint: string;
  icon: IconName;
  /** The text colour every icon in this group takes, header and rows alike. */
  iconClass: string;
  items: VerificationItem[];
}

/**
 * The four groups, in the order a reader needs them.
 *
 * Contradicted sits above could-not-verify because it is the only state that
 * means the evidence *disagreed with the posting* rather than merely failing to
 * confirm it. Reading order follows urgency, not the enum.
 *
 * All four are returned whether or not they are populated; the caller drops the
 * empty ones. An absent group and an empty one are different signals — absent
 * means no check landed there, empty would mean a check ran and returned nothing
 * — and only the former is currently expressible.
 */
const GROUPS: Record<CheckState, Omit<Group, 'items'>> = {
  contradicted: {
    key: 'contradicted',
    label: 'Contradicted',
    chip: 'chip-critical',
    tint: 'status-card-critical',
    icon: 'gpp_bad',
    iconClass: 'text-chip-critical-text',
  },
  confirmed: {
    key: 'confirmed',
    label: 'Confirmed',
    chip: 'chip-verified',
    tint: 'status-card-verified',
    icon: 'gpp_good',
    iconClass: 'text-chip-verified-text',
  },
  supported: {
    key: 'supported',
    label: 'Named in the record',
    chip: 'chip-verified',
    tint: 'status-card-verified',
    // A tick rather than the verified shield. The shield says the claim was
    // checked and held; a tick says something exists. `supported` is the second
    // sentence, and the two must not render identically or the distinction is
    // invisible.
    icon: 'check_circle',
    iconClass: 'text-chip-verified-text',
  },
  unknown: {
    key: 'unknown',
    label: 'Could not verify',
    chip: 'chip-caution',
    tint: 'status-card-caution',
    // A circled question mark, not `gpp_maybe`. That glyph is a shield with an
    // exclamation point inside, and in this column it would be a claim about
    // the employer: a shield-and-bang announces a problem with someone. The
    // claim here is narrower and must stay narrower — the check ran and
    // established nothing either way. "Unknown" and "alarm" are different
    // sentences, and this product's standing rule is not to assert what it
    // cannot support.
    icon: 'question_mark',
    iconClass: 'text-chip-caution-text',
  },
};

/** The reading order. Contradicted first, then the two confirmations, then silence. */
const GROUP_ORDER: CheckState[] = ['contradicted', 'confirmed', 'supported', 'unknown'];

export function groupBy(items: VerificationItem[]): Group[] {
  const buckets: Record<CheckState, VerificationItem[]> = {
    confirmed: [],
    supported: [],
    contradicted: [],
    unknown: [],
  };
  for (const item of items) {
    const state = groupFor(item.status);
    buckets[state].push(item);
  }
  return GROUP_ORDER.map((key) => ({ ...GROUPS[key], items: buckets[key] }));
}

/**
 * The bucket a state belongs in.
 *
 * An unrecognised state — a stored reading written before this vocabulary, or a
 * provider answering outside it — lands on `unknown` rather than being dropped.
 * A check the panel cannot classify is a check it could not settle, and silence
 * would hide a card the reader was already shown.
 */
function groupFor(status: VerificationItem['status']): CheckState {
  if (status === 'confirmed' || status === 'supported' || status === 'contradicted') {
    return status;
  }
  return 'unknown';
}

/** Which icon and colour one individual check takes, from its own state. */
export function statusPresentation(status: VerificationItem['status']): { icon: IconName; cls: string } {
  const group = GROUPS[groupFor(status)];
  return { icon: group.icon, cls: group.iconClass };
}
