import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor, act } from '@testing-library/react';
import React from 'react';
import { ScanActions } from './ScanActions';
import { riskAccent } from '../../lib/riskAccent';

afterEach(cleanup);

function button(): HTMLElement {
  // The icon renders a ligature as text, so the accessible name is
  // "touch_appPick a Job Post" rather than the label alone. The label also
  // varies with picker state.
  return screen.getByRole('button', { name: /Pick a Job Post|Pick again|Cancel Selection/ });
}

describe('ScanActions risk accent', () => {
  it('stays gold with no result on screen', () => {
    render(React.createElement(ScanActions, {}));
    expect(button().className).toContain('tactile-btn-gold');
  });

  it('takes the risk fill for a high or critical result', () => {
    render(React.createElement(ScanActions, { accent: riskAccent('critical') }));
    const cls = button().className;
    expect(cls).toContain('error-container');
    // The gold fill and its inset highlight go together; keeping the
    // tactile shadow over a flat error wash leaves a visible edge.
    expect(cls).not.toContain('tactile-btn-gold');
  });

  it('returns to gold when the accent is withdrawn', () => {
    const { rerender } = render(
      React.createElement(ScanActions, { accent: riskAccent('high') })
    );
    expect(button().className).toContain('error-container');

    // This is the "temporary" half: the parent stops passing an accent the
    // moment a new element is picked, and the button must follow with no
    // timer of its own.
    rerender(React.createElement(ScanActions, { accent: undefined }));
    expect(button().className).toContain('tactile-btn-gold');
  });

  it('keeps the picker-active styling over the risk accent', () => {
    // Cancelling a pick is a direct instruction from the reader and must stay
    // the loudest thing on the button.
    render(React.createElement(ScanActions, { accent: riskAccent('critical'), isPickerActive: true }));
    expect(button().className).toContain('hover:bg-error/30');
  });
});
