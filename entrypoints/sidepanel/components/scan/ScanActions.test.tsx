import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, act, fireEvent } from '@testing-library/react';
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


describe('the Advanced-scan toggle', () => {
  function toggle(container: HTMLElement): HTMLInputElement | null {
    return container.querySelector('[data-role="advanced-scan"] input[type="checkbox"]');
  }

  function box(container: HTMLElement): HTMLElement | null {
    return container.querySelector('[data-role="advanced-scan"] span[aria-hidden]');
  }

  it('renders only when the session owns the setting', () => {
    const { container } = render(React.createElement(ScanActions, {}));
    expect(container.querySelector('[data-role="advanced-scan"]')).toBeNull();
  });

  it('starts unchecked and reports the toggle through the setter', () => {
    const onAdvancedScanChange = vi.fn();
    const { container } = render(
      React.createElement(ScanActions, {
        advancedScan: false,
        onAdvancedScanChange,
      })
    );

    const input = toggle(container);
    expect(input?.checked).toBe(false);

    fireEvent.click(input!);
    expect(onAdvancedScanChange).toHaveBeenCalledWith(true);
  });

  it('draws the checked box filled, unchecked box empty', () => {
    // The fill is the animation: border and wash shift with the state over
    // 200ms, so the class list is what is asserted — happy-dom performs no
    // transitions, exactly like the ScanActions accent tests.
    const on = render(React.createElement(ScanActions, { advancedScan: true, onAdvancedScanChange: vi.fn() }));
    expect(box(on.container)?.className).toContain('bg-secondary');
    expect(box(on.container)?.className).toContain('border-secondary');

    const off = render(React.createElement(ScanActions, { advancedScan: false, onAdvancedScanChange: vi.fn() }));
    expect(box(off.container)?.className).toContain('bg-surface-container-low');
    expect(box(off.container)?.className).not.toContain('bg-secondary');
  });

  it('names the cost in the disclaimer', () => {
    const { container } = render(React.createElement(ScanActions, { advancedScan: false, onAdvancedScanChange: vi.fn() }));
    const text = container.querySelector('[data-role="advanced-scan"]')?.textContent ?? '';
    expect(text).toMatch(/Advanced scan/i);
    expect(text).toMatch(/few minutes/i);
  });

  it('renders disabled when the scan controls are disabled', () => {
    const { container } = render(
      React.createElement(ScanActions, { advancedScan: false, onAdvancedScanChange: vi.fn(), disabled: true })
    );
    expect(toggle(container)?.disabled).toBe(true);
  });
});