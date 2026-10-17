import type { IconName } from '../common';
import type { VerificationItem } from '../../types';

/**
 * How one verification check is grouped and marked, in both places it appears.
 *
 * **Extracted because a check is now shown twice, and the two renderings have to
 * agree.** `WhatWeChecked` shows the label alone, in a three-bucket column;
 * `FullDetails` shows the same checks with the model's sentence under each one.
 * The reader correlates them by eye — the words *Channel Match* in a red bucket
 * above are matched to the paragraph explaining them below — and that
 * correlation is the entire point. Two copies of the grouping would let a status
 * read green above and be filed under "Could not verify" below, which is worse
 * than not showing the sentence at all.
 *
 * Nothing here decides *which* checks are visible. That is `shouldShowCheck` in
 * `lib/riskDisplay`, shared by both components for the same reason; this module
 * only says how a check already admitted is marked.
 */
export interface Group {
  key: 'verified' | 'contradicted' | 'unverified';
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
 * The three groups, in the order a reader needs them.
 *
 * Contradicted sits above could-not-verify because a `red` is the only status
 * that means the evidence *disagreed with the posting* rather than merely failing
 * to confirm it. Reading order follows urgency, not the status enum.
 *
 * All three are returned whether or not they are populated; the caller drops the
 * empty ones. An absent group and an empty one are different signals — absent
 * means no check landed there, empty would mean a check ran and returned nothing
 * — and only the former is currently expressible.
 */
export function groupBy(items: VerificationItem[]): Group[] {
  const green: VerificationItem[] = [];
  const yellow: VerificationItem[] = [];
  const red: VerificationItem[] = [];
  for (const item of items) {
    if (item.status === 'green') green.push(item);
    else if (item.status === 'red') red.push(item);
    else yellow.push(item);
  }
  return [
    {
      key: 'verified',
      label: 'Verified',
      chip: 'chip-verified',
      tint: 'status-card-verified',
      icon: 'gpp_good',
      iconClass: 'text-chip-verified-text',
      items: green,
    },
    {
      key: 'contradicted',
      label: 'Contradicted',
      chip: 'chip-critical',
      tint: 'status-card-critical',
      icon: 'gpp_bad',
      iconClass: 'text-chip-critical-text',
      items: red,
    },
    {
      key: 'unverified',
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
      items: yellow,
    },
  ];
}

/** Which icon and colour one individual check takes, from its own status. */
export function statusPresentation(status: VerificationItem['status']): { icon: IconName; cls: string } {
  switch (status) {
    case 'green':
      return { icon: 'gpp_good', cls: 'text-chip-verified-text' };
    case 'red':
      return { icon: 'gpp_bad', cls: 'text-chip-critical-text' };
    case 'yellow':
    default:
      return { icon: 'question_mark', cls: 'text-chip-caution-text' };
  }
}