import { describe, it, expect } from 'vitest';
import { riskAccent, ELEVATED_LEVELS } from './riskAccent';
import type { ScanRiskLevel } from '../types';

describe('riskAccent', () => {
  it('paints high and critical in the danger token', () => {
    expect(riskAccent('high').text).toBe('text-error');
    expect(riskAccent('critical').text).toBe('text-error');
  });

  it('paints moderate in the caution token', () => {
    expect(riskAccent('moderate').text).toBe('text-tertiary');
  });

  it('leaves low and unmeasured unaccented', () => {
    // Accenting a low score would spend the panel's loudest signal on the
    // least urgent outcome, which is what the reader learns to ignore.
    expect(riskAccent('low').text).toBe('');
    expect(riskAccent(null).text).toBe('');
  });

  it('tints the button background only for elevated levels', () => {
    expect(riskAccent('critical').button).not.toBe('');
    expect(riskAccent('high').button).not.toBe('');
    expect(riskAccent('moderate').button).toBe('');
    expect(riskAccent('low').button).toBe('');
    expect(riskAccent(null).button).toBe('');
  });

  it('tints card borders for elevated levels', () => {
    expect(riskAccent('high').border).toContain('border-error');
  });

  it('keeps a softer border for moderate but no button tint', () => {
    // A border is a quiet signal and moderate warrants one. The button is the
    // loudest element on the panel, and spending it on a mid score would train
    // the reader to ignore it before a real high risk arrives.
    expect(riskAccent('moderate').border).toContain('border-tertiary');
    expect(riskAccent('moderate').button).toBe('');
  });

  it('never returns a raw hex value', () => {
    // The design system is token-based; a literal would drift from light/dark.
    for (const level of ['low', 'moderate', 'high', 'critical', null] as (ScanRiskLevel | null)[]) {
      const a = riskAccent(level);
      for (const value of [a.text, a.button, a.border, a.surface]) {
        expect(value).not.toMatch(/#[0-9a-f]{3,6}/i);
        expect(value).not.toMatch(/hsl\(/);
      }
    }
  });

  it('names exactly the levels that promote the evidence', () => {
    expect([...ELEVATED_LEVELS].sort()).toEqual(['critical', 'high']);
  });
});
