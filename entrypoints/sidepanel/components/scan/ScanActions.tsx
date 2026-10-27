import React from 'react';
import { Icon } from '../common/Icon';
import {
  PICK_ELEMENT_LABEL,
  PICK_ELEMENT_ACTIVE_LABEL,
  PICK_ELEMENT_CANCEL_LABEL,
  PICK_AGAIN_LABEL,
} from '../../data/content';
import type { Accent } from '../../lib/riskAccent';

export interface ScanActionsProps {
  onPickElement?: () => void;
  onCancelPick?: () => void;
  isPickerActive?: boolean;
  isPickerActivating?: boolean;
  onManualCrop?: () => void;
  onCancelCrop?: () => void;
  isCropActive?: boolean;
  isCropActivating?: boolean;
  afterScan?: boolean;
  disabled?: boolean;
  /**
   * Risk colour for the primary button, for as long as a result is on screen.
   *
   * Scoped to the currently displayed result, which is what makes it
   * temporary: picking a new element clears the scan result, the accent prop
   * goes with it, and the button returns to the accent colour without a timer of its own.
   * A button that stayed red after the result was gone would describe the
   * next scan rather than the one on screen.
   */
  accent?: Accent;
  /** The Advanced-scan toggle's state and setter, owned by the session. */
  advancedScan?: boolean;
  onAdvancedScanChange?: (value: boolean) => void;
}

export function ScanActions({
  onPickElement,
  onCancelPick,
  isPickerActive = false,
  isPickerActivating = false,
  onManualCrop,
  onCancelCrop,
  isCropActive = false,
  isCropActivating = false,
  afterScan = false,
  disabled = false,
  accent,
  advancedScan = false,
  onAdvancedScanChange,
}: ScanActionsProps) {
  const handlePickToggle = () => {
    if (isPickerActive) {
      onCancelPick?.();
    } else {
      onPickElement?.();
    }
  };

  const handleCropToggle = () => {
    if (isCropActive) {
      onCancelCrop?.();
    } else {
      onManualCrop?.();
    }
  };

  return (
    // order-3, with the reasoning recorded at the call site: the parent is a
    // flex column whose result groups carry order-1/order-2, so an un-ordered
    // child would sort ahead of them and break this bar's stickiness.
    <div className="sticky bottom-0 left-0 right-0 z-30 order-3 p-3 -mx-container-padding mt-auto">
      <div className="flex gap-2">
        <button
          onClick={handlePickToggle}
          disabled={isPickerActivating || disabled}
          data-role="pick-element"
          className={`flex-1 py-2.5 rounded-lg font-label-md flex items-center justify-center gap-2 transition-all active:translate-y-[1px] tactile-btn-accent py-3 rounded-lg text-body-md disabled:opacity-70 ${
            isPickerActive
              ? 'bg-error/20 text-error border border-error/30 hover:bg-error/30'
              // A modifier on the tactile class, applied alongside it. The
              // accent is only ever the colour: the 3D treatment stays so the
              // primary action does not change shape at the moment it changes
              // message.
              : accent?.button ?? ''
          }`}
        >
          <Icon
            name="touch_app"
            className={isPickerActivating ? 'animate-pulse' : ''}
          />
          {isPickerActivating
            ? PICK_ELEMENT_ACTIVE_LABEL
            : isPickerActive
              ? PICK_ELEMENT_CANCEL_LABEL
              : afterScan
                ? PICK_AGAIN_LABEL
                : PICK_ELEMENT_LABEL}
        </button>

        {!afterScan && (
          <button
            onClick={handleCropToggle}
            disabled={isCropActivating || disabled}
            className={`flex-1 py-2.5 rounded-lg text-label-md font-label flex items-center justify-center gap-2 transition-all active:translate-y-[1px] ${
              isCropActive
                ? 'bg-error/20 text-error border border-error/30 hover:bg-error/30'
                : 'btn-outline-accent bg-background'
            }`}
          >
            <Icon
              name="crop"
              className={isCropActivating ? 'animate-pulse' : ''}
            />
            {isCropActivating
              ? 'Selecting...'
              : isCropActive
                ? 'Cancel Crop'
                : 'Manual Crop'}
          </button>
        )}
      </div>

      {advancedScanToggle(advancedScan, onAdvancedScanChange, disabled)}
    </div>
  );
}

/**
 * The Advanced-scan toggle, below the scan controls.
 *
 * **What it actually does, said plainly.** On: the scan model's reasoning is
 * turned on for this one request, so the prompt's do-not-flag rules are
 * deliberated over instead of skimmed — the difference that retired a false
 * positive on an ordinary DM application. The cost is minutes, which is the
 * disclaimer's job to name before the reader commits.
 *
 * Rendered by a function rather than inline so the scan controls above stay
 * one visual block: the toggle is a setting, not a second action.
 */
function advancedScanToggle(
  advancedScan: boolean,
  onAdvancedScanChange: ((value: boolean) => void) | undefined,
  disabled: boolean,
) {
  if (!onAdvancedScanChange) return null;
  return (
    // The whole row is a card, like the panel's notice blocks — a bare native
    // checkbox read as unstyled HTML pasted under a tactile button. The fill
    // on toggle is the row itself: border and wash shift with the state over
    // 200ms, which is the "fill animation" the first version lacked.
    <label
      data-role="advanced-scan"
      className={`mt-3 flex items-start gap-3 rounded-lg border px-3 py-2.5 transition-colors duration-200 ${
        disabled ? 'opacity-60' : 'cursor-pointer'
      } ${
        advancedScan
          ? 'border-secondary/30 bg-secondary/10'
          : 'border-outline-variant/20 bg-surface-container-lowest'
      }`}
    >
      {/* sr-only input + a drawn box: a native checkbox has no fill animation
          to transition, and accent-color alone cannot animate. The input keeps
          the semantics and the keyboard; the box is drawn and driven by the
          same state, so they can never disagree. */}
      <input
        type="checkbox"
        checked={advancedScan}
        disabled={disabled}
        onChange={(e) => onAdvancedScanChange(e.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition-all duration-200 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-secondary ${
          advancedScan
            ? 'border-secondary bg-secondary'
            : 'border-outline-variant bg-surface-container-low'
        }`}
      >
        <Icon
          name="check"
          className={`h-3.5 w-3.5 text-on-secondary transition-all duration-200 ${
            advancedScan ? 'scale-100 opacity-100' : 'scale-50 opacity-0'
          }`}
        />
      </span>
      <span className="min-w-0">
        <span className="block text-label-md font-label font-semibold text-on-surface leading-tight">
          Advanced scan
        </span>
        <span className="mt-0.5 block text-body-sm text-on-surface-variant leading-snug">
          The model thinks through the posting before answering, for a more
          careful read. It might take a few minutes.
        </span>
      </span>
    </label>
  );
}
export default ScanActions;
