import { describe, it, expect } from 'vitest';
import { riskAccent, ELEVATING_RULES, isElevated } from './riskAccent';
import type { Assessment } from '../types';

describe('riskAccent', () => {
  it('gives red the elevated tone', () => {
    expect(riskAccent('red').text).toBe('text-error');
  });

  it('gives yellow the caution tone', () => {
    expect(riskAccent('yellow').text).toBe('text-tertiary');
  });

  it('gives green no accent', () => {
    expect(riskAccent('green').text).toBe('');
  });

  it('gives nothing no accent', () => {
    expect(riskAccent(null).text).toBe('');
  });

  it('red gets the full button treatment', () => {
    expect(riskAccent('red').button).not.toBe('');
  });

  it('yellow gets no button treatment', () => {
    expect(riskAccent('yellow').button).toBe('');
  });

  it('green gets no button treatment', () => {
    expect(riskAccent('green').button).toBe('');
  });

  it('red carries the error border', () => {
    expect(riskAccent('red').border).toContain('border-error');
  });

  it('yellow carries the caution border', () => {
    expect(riskAccent('yellow').border).toContain('border-tertiary');
  });

  it('yellow elevates to the error tone only for the scam-shape rule', () => {
    expect(
      riskAccent('yellow', 'prohibited_at_unestablished_employer').text,
    ).toBe('text-error');
    expect(riskAccent('yellow', 'unclassified_request').text).toBe('text-tertiary');
    expect(riskAccent('yellow').text).toBe('text-tertiary');
  });

  it('elevation covers every assessment and the absence', () => {
    for (const assessment of ['green', 'yellow', 'red', null] as (Assessment | null)[]) {
      expect(() => riskAccent(assessment)).not.toThrow();
    }
  });

  it('elevating rules are named, not colours', () => {
    expect([...ELEVATING_RULES]).toEqual(['prohibited_at_unestablished_employer']);
  });

  it('isElevated matches the accent decision', () => {
    expect(isElevated('red')).toBe(true);
    expect(isElevated('yellow', 'prohibited_at_unestablished_employer')).toBe(true);
    expect(isElevated('yellow')).toBe(false);
    expect(isElevated('green')).toBe(false);
  });
});
