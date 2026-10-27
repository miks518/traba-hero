import type { Assessment } from '../types';

/**
 * Risk colour for chrome, not for prose.
 *
 * Every value here is a Tailwind token so light and dark both resolve from the
 * same class. No literal hex or hsl: RiskGauge already uses inline hsl for the
 * ring, but that is an SVG stroke the token system cannot express, and copying
 * it here would pin one theme's values into both.
 *
 * `text` and `surface` are for headers and accents. Body prose deliberately has
 * no entry: long blocks of red or amber on a light surface are the hardest
 * thing on the panel to read, and this is where someone reads a assessment
 * carefully enough to act on it.
 */
export interface Accent {
  /** Header, label, and icon tint. */
  text: string;
  /** Background wash for a tinted panel or card. */
  surface: string;
  /** Border for a card that should read as a warning. */
  border: string;
  /** Full class set for the primary action button. */
  button: string;
}

const NONE: Accent = { text: '', surface: '', border: '', button: '' };

const ELEVATED: Accent = {
  text: 'text-error',
  surface: 'bg-error-container/10',
  border: 'border-error/40',
  // A *modifier* on `tactile-btn-accent`, not a replacement for it. This used to
  // be a flat fill, which meant a high or critical result turned the primary
  // action from an extruded key into a flat button: the affordance changed at
  // the same moment as the message. `.tactile-btn-accent.tactile-btn-error` moves
  // one CSS variable instead, so the gradient, the extrusion, the top highlight,
  // and the press animation are identical in both states by construction.
  button: 'tactile-btn-error',
};

const CAUTION: Accent = {
  text: 'text-tertiary',
  surface: 'bg-tertiary-container/10',
  border: 'border-tertiary/40',
  button: '',
};

/** The grid rule that makes a yellow lead with the evidence.
 *
 * Yellow is uncertainty, and most of it stays the quiet caution tone. The one
 * exception is the scam shape — a prohibited request at an employer the record
 * never established — where the chip says "Caution" but the panel leads with
 * what was and was not found, because that is the reading a jobseeker most
 * needs to see before they reply.
 */
export const ELEVATING_RULES = ['prohibited_at_unestablished_employer'] as const;

export function isElevated(
  assessment: Assessment | null | undefined,
  rule?: string,
): boolean {
  if (assessment === 'red') return true;
  return assessment === 'yellow' && !!rule && (ELEVATING_RULES as readonly string[]).includes(rule);
}

export function riskAccent(
  assessment: Assessment | null | undefined,
  rule?: string,
): Accent {
  if (isElevated(assessment, rule)) return ELEVATED;
  if (assessment === 'yellow') return CAUTION;
  return NONE;
}