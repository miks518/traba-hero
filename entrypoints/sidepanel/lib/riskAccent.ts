import type { ScanRiskLevel } from '../types';

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
 * thing on the panel to read, and this is where someone reads a verdict
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

const MODERATE: Accent = {
  text: 'text-tertiary',
  surface: 'bg-tertiary-container/10',
  border: 'border-tertiary/40',
  button: '',
};

/** The levels whose evidence is promoted to the top. */
export const ELEVATED_LEVELS = ['high', 'critical'] as const;

export function isElevated(level: ScanRiskLevel | null | undefined): boolean {
  return level === 'high' || level === 'critical';
}

export function riskAccent(level: ScanRiskLevel | null | undefined): Accent {
  if (isElevated(level)) return ELEVATED;
  if (level === 'moderate') return MODERATE;
  return NONE;
}
