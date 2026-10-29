// The consent notice, before a resume is ever uploaded.
//
// RA 10173 consent has to be informed, specific and voluntary. These tests pin
// the disclosures that make it so — what is read, where it travels, what is
// kept, that declining costs nothing, and where a complaint goes — so a copy
// edit cannot quietly hollow the notice out. The retention sentence is
// enforced by backend/tests/test_resume_content_not_logged.py, which is why it
// is allowed to say "no database copy is written" in as many words.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import React from 'react';
import { ConsentModal } from './ConsentModal';

afterEach(cleanup);

function renderModal(open = true, handlers = {}) {
  const props = { open, fileName: 'jane_resume.pdf', onAccept: vi.fn(), onDecline: vi.fn(), ...handlers };
  render(React.createElement(ConsentModal, props));
  return props;
}

describe('ConsentModal', () => {
  it('renders nothing when closed', () => {
    renderModal(false);
    expect(screen.queryByText(/before we process your resume/i)).toBeNull();
  });

  it('names the file and says nothing has been sent yet', () => {
    renderModal();
    expect(screen.getByText(/jane_resume\.pdf/)).toBeTruthy();
    expect(screen.getByText(/nothing has been sent yet/i)).toBeTruthy();
  });

  it('says what is read: the whole document', () => {
    renderModal();
    expect(screen.getByText(/everything the file contains/i)).toBeTruthy();
  });

  it('says where it travels: the Trabahero server and a third-party AI provider', () => {
    renderModal();
    expect(screen.getByText(/Trabahero server/i)).toBeTruthy();
    expect(screen.getByText(/third-party AI provider/i)).toBeTruthy();
  });

  it('says what is kept: processed in memory, no database copy, session-only profile', () => {
    renderModal();
    expect(screen.getByText(/processed in memory/i)).toBeTruthy();
    expect(screen.getByText(/no database copy/i)).toBeTruthy();
    expect(screen.getByText(/while the panel is open/i)).toBeTruthy();
  });

  it('says consent is voluntary and names the way out and the law', () => {
    renderModal();
    expect(screen.getByText(/voluntary/i)).toBeTruthy();
    expect(screen.getByText(/enter your skills manually/i)).toBeTruthy();
    expect(screen.getByText(/RA 10173/i)).toBeTruthy();
    expect(screen.getByText(/National Privacy Commission/i)).toBeTruthy();
  });

  it('accepts and declines through the two buttons', () => {
    const props = renderModal();

    fireEvent.click(screen.getByRole('button', { name: /don't upload/i }));
    expect(props.onDecline).toHaveBeenCalledTimes(1);
    expect(props.onAccept).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /agree & upload/i }));
    expect(props.onAccept).toHaveBeenCalledTimes(1);
  });
});
