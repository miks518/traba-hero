import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, act, fireEvent } from '@testing-library/react';
import React from 'react';
import { ScanActions } from './ScanActions';
import { riskAccent } from '../../lib/riskAccent';

afterEach(cleanup);

function button(): HTMLElement {
  // The icon renders a ligature as text, so the accessible name is
  // "touch_appPick a Job Post" rather than the label alone. The label also
  // varies with picker state and with whether images are already captured.
  return screen.getByRole('button', { name: /Pick a Job Post|Pick More|Pick again|Cancel Selection/ });
}

describe('ScanActions risk accent', () => {
  it('stays accent-coloured with no result on screen', () => {
    render(React.createElement(ScanActions, {}));
    expect(button().className).toContain('tactile-btn-accent');
  });

  it('keeps its 3D shape and only changes colour for a stop or caution result', () => {
    // This used to assert the opposite. The accent replaced the whole class
    // string, so a high-risk result turned the primary action from an extruded
    // accent key into a flat error wash. The colour is meant to carry the risk;
    // the affordance is not part of that message and changing it at the same
    // moment as the message makes the button harder to aim at.
    render(React.createElement(ScanActions, { accent: riskAccent('red') }));
    const cls = button().className;
    expect(cls).toContain('tactile-btn-accent');
    expect(cls).toContain('tactile-btn-error');
  });

  it('the accent and the error states share one tactile class, not two buttons', () => {
    // Proves the recolour is a modifier on the same element: the base class is
    // present in both states, so the 3D treatment cannot have been swapped out.
    const { rerender } = render(React.createElement(ScanActions, {}));
    const accented = button().className;

    rerender(React.createElement(ScanActions, { accent: riskAccent('red') }));
    const red = button().className;

    expect(accented).toContain('tactile-btn-accent');
    expect(accented).not.toContain('tactile-btn-error');
    expect(red).toContain('tactile-btn-accent');
    expect(red).toContain('tactile-btn-error');
  });

  it('returns to the accent colour when the accent is withdrawn', () => {
    const { rerender } = render(
      React.createElement(
        ScanActions,
        { accent: riskAccent('yellow', 'prohibited_at_unestablished_employer') }
      )
    );
    expect(button().className).toContain('tactile-btn-error');

    // This is the "temporary" half: the parent stops passing an accent the
    // moment a new element is picked, and the button must follow with no
    // timer of its own.
    rerender(React.createElement(ScanActions, { accent: undefined }));
    expect(button().className).toContain('tactile-btn-accent');
    expect(button().className).not.toContain('tactile-btn-error');
  });

  it('keeps the picker-active styling over the risk accent', () => {
    // Cancelling a pick is a direct instruction from the reader and must stay
    // the loudest thing on the button.
    render(React.createElement(ScanActions, { accent: riskAccent('red'), isPickerActive: true }));
    expect(button().className).toContain('hover:bg-error/30');
  });
});


describe('the primary button label', () => {
  it('reads "Pick a Job Post" while nothing is captured', () => {
    render(React.createElement(ScanActions, {}));
    expect(screen.getByRole('button', { name: /Pick a Job Post/ })).toBeTruthy();
  });

  it('reads "Pick More" once an image is captured and waiting', () => {
    // The first capture is behind the reader, so the button should name the
    // action that remains: adding another image to the set.
    render(React.createElement(ScanActions, { hasScreenshots: true }));
    expect(screen.getByRole('button', { name: /Pick More/ })).toBeTruthy();
  });

  it('keeps "Cancel Selection" over "Pick More" while the picker is open', () => {
    render(React.createElement(ScanActions, { hasScreenshots: true, isPickerActive: true }));
    expect(screen.getByRole('button', { name: /Cancel Selection/ })).toBeTruthy();
  });

  it('keeps "Pick again" over "Pick More" after a scan', () => {
    render(React.createElement(ScanActions, { hasScreenshots: true, afterScan: true }));
    expect(screen.getByRole('button', { name: /Pick again/ })).toBeTruthy();
  });
});


describe('the Advanced-scan toggle', () => {
  function row(container: HTMLElement): HTMLElement | null {
    return container.querySelector('[data-role="advanced-scan"]');
  }

  function switchButton(container: HTMLElement): HTMLButtonElement | null {
    return container.querySelector('[data-role="advanced-switch"]');
  }

  function knob(container: HTMLElement): HTMLElement | null {
    return container.querySelector('[data-role="advanced-switch"] span[aria-hidden]');
  }

  it('renders only when the session owns the setting', () => {
    const { container } = render(React.createElement(ScanActions, {}));
    expect(container.querySelector('[data-role="advanced-scan"]')).toBeNull();
  });

  it('is a container row: tactile-card, and the switch is the control', () => {
    // DESIGN.md's two tiers: the row holds information and carries the
    // container slab; the operable element is the switch itself.
    const { container } = render(React.createElement(ScanActions, { advancedScan: false, onAdvancedScanChange: vi.fn() }));
    expect(row(container)?.className).toContain('tactile-card');
    const button = switchButton(container);
    expect(button?.getAttribute("role")).toBe("switch");
    expect(button?.getAttribute("aria-checked")).toBe("false");
  });

  it('toggles through the setter, to the opposite of the current state', () => {
    const onAdvancedScanChange = vi.fn();
    const { container } = render(React.createElement(ScanActions, { advancedScan: false, onAdvancedScanChange }));

    fireEvent.click(switchButton(container)!);
    expect(onAdvancedScanChange).toHaveBeenCalledWith(true);
  });

  it('wears the accent when on, and the knob slides', () => {
    // DESIGN.md's Toggle Switch: 40x24, accent checked state. The track is
    // asserted by class — happy-dom performs no transitions, exactly like
    // the ScanActions accent tests.
    const on = render(React.createElement(ScanActions, { advancedScan: true, onAdvancedScanChange: vi.fn() }));
    expect(switchButton(on.container)?.className).toContain('bg-secondary');
    expect(knob(on.container)?.className).toContain('translate-x-4');

    const off = render(React.createElement(ScanActions, { advancedScan: false, onAdvancedScanChange: vi.fn() }));
    expect(switchButton(off.container)?.className).toContain('bg-surface-container-highest');
    expect(knob(off.container)?.className).toContain('translate-x-0');
  });

  it('names the cost in the disclaimer', () => {
    const { container } = render(React.createElement(ScanActions, { advancedScan: false, onAdvancedScanChange: vi.fn() }));
    const text = row(container)?.textContent ?? '';
    expect(text).toMatch(/Advanced scan/i);
    expect(text).toMatch(/few minutes/i);
  });

  it('is hidden while a scan is running', () => {
    // Once the request has gone out, flipping the setting would promise
    // something it cannot deliver — the thinking flag was already sent. The
    // toggle disappears with the controls and returns when they do.
    const { container } = render(
      React.createElement(ScanActions, { advancedScan: false, onAdvancedScanChange: vi.fn(), disabled: true })
    );
    expect(row(container)).toBeNull();
  });
});