import { describe, it, expect } from 'vitest';
import { riskAccent, ELEVATED_ASSESSMENTS } from './riskAccent';
import type { Assessment } from '../types';

describe('riskAccent', () => {
  it('paints stop and caution in the danger token', () => {
    expect(riskAccent('stop').text).toBe('text-error');
    expect(riskAccent('caution').text).toBe('text-error');
  });

  it('paints note in the caution token', () => {
    expect(riskAccent('note').text).toBe('text-tertiary');
  });

  it('leaves clear and unmeasured unaccented', () => {
    // Accenting a clear assessment would spend the panel's loudest signal on the
    // least urgent outcome, which is what the reader learns to ignore.
    expect(riskAccent('clear').text).toBe('');
    expect(riskAccent(null).text).toBe('');
  });

  it('tints the button background only for elevated assessments', () => {
    expect(riskAccent('stop').button).not.toBe('');
    expect(riskAccent('caution').button).not.toBe('');
    expect(riskAccent('note').button).toBe('');
    expect(riskAccent('clear').button).toBe('');
    expect(riskAccent(null).button).toBe('');
  });

  it('tints card borders for elevated assessments', () => {
    expect(riskAccent('stop').border).toContain('border-error');
  });

  it('keeps a softer border for note but no button tint', () => {
    // A border is a quiet signal and note warrants one. The button is the
    // loudest element on the panel, and spending it on a note assessment would
    // train the reader to ignore it before a real stop arrives.
    expect(riskAccent('note').border).toContain('border-tertiary');
    expect(riskAccent('note').button).toBe('');
  });

  it('never returns a raw hex value', () => {
    // The design system is token-based; a literal would drift from light/dark.
    for (const assessment of ['clear', 'note', 'caution', 'stop', null] as (Assessment | null)[]) {
      const a = riskAccent(assessment);
      for (const value of [a.text, a.button, a.border, a.surface]) {
        expect(value).not.toMatch(/#[0-9a-f]{3,6}/i);
        expect(value).not.toMatch(/hsl\(/);
      }
    }
  });

  it('names exactly the assessments that promote the evidence', () => {
    expect([...ELEVATED_ASSESSMENTS].sort()).toEqual(['caution', 'stop']);
  });
});