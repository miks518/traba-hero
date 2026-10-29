// The Privacy link's destination comes from the build env.
//
// The footer has displayed "Privacy" since it shipped with nowhere to go — a
// pointer cursor over an inert span. The destination is not ours to invent: no
// domain hosts a policy, so the link reads `WXT_PRIVACY_POLICY_URL` at build
// time and goes live the moment a value is pasted. Until then it renders, per
// AC-05, as the same inert text it has always been.
//
// These tests stub the env because happy-dom cannot click through to a real
// tab anyway — the contract is the anchor, its href, and its target.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import React from 'react';
import { Footer } from './Footer';

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe('the Privacy link', () => {
  it('opens the configured policy URL in a new tab', () => {
    vi.stubEnv('WXT_PRIVACY_POLICY_URL', 'https://example.com/privacy-policy');
    render(React.createElement(Footer));

    const link = screen.getByRole('link', { name: 'Privacy' });
    expect(link.getAttribute('href')).toBe('https://example.com/privacy-policy');
    expect(link.getAttribute('target')).toBe('_blank');
    // A tab the extension opened must not hand it the opener reference.
    expect(link.getAttribute('rel')).toContain('noreferrer');
  });

  it('renders as inert text while no URL is configured, but still displays', () => {
    // AC-05: the footer displays Legal and Privacy. An unset env hides the
    // destination, not the link — the label stays so the promise is visible
    // and the criterion holds; it just cannot go anywhere yet.
    vi.stubEnv('WXT_PRIVACY_POLICY_URL', '');
    render(React.createElement(Footer));

    expect(screen.queryByRole('link', { name: 'Privacy' })).toBeNull();
    expect(screen.getByText('Privacy')).toBeTruthy();
  });

  it('never turns Legal into a link — it has no destination either', () => {
    vi.stubEnv('WXT_PRIVACY_POLICY_URL', 'https://example.com/privacy-policy');
    render(React.createElement(Footer));

    expect(screen.queryByRole('link', { name: 'Legal' })).toBeNull();
    expect(screen.getByText('Legal')).toBeTruthy();
  });
});
