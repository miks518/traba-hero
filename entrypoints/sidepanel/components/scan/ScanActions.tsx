import React from 'react';
import { Icon } from '../common/Icon';
import {
  PICK_ELEMENT_LABEL,
  PICK_ELEMENT_ACTIVE_LABEL,
  PICK_ELEMENT_CANCEL_LABEL,
  PICK_MORE_LABEL,
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
  /**
   * At least one image is captured and waiting to be scanned.
   *
   * The primary button then reads "Pick More" instead of "Pick a Job Post":
   * the first capture is no longer ahead of the reader, so the button should
   * say what pressing it does now — add another image to the set — rather than
   * describe a step that already happened. Losing to `afterScan` and the
   * picker states is deliberate: "Pick again" and "Cancel Selection" name the
   * moment the reader is actually in.
   */
  hasScreenshots?: boolean;
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
  hasScreenshots = false,
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
                : hasScreenshots
                  ? PICK_MORE_LABEL
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
 * The Advanced-scan setting, below the scan controls.
 *
 * **What it actually does, said plainly.** On: the scan model's reasoning is
 * turned on for this one request, so the prompt's do-not-flag rules are
 * deliberated over instead of skimmed — the difference that retired a false
 * positive on an ordinary DM application. The cost is minutes, which is the
 * disclaimer's job to name before the reader commits.
 *
 * **The two-tier rule decides the shapes here** (DESIGN.md, "Hard shadow"):
 * the row holds information — a container, so it wears the tactile-card slab
 * and never presses; the operable element is the switch, a button, and the
 * press lives on it. The switch itself is DESIGN.md's Toggle Switch
 * component: 40x24, accent checked state, knob slides on 200ms.
 */
function advancedScanToggle(
  advancedScan: boolean,
  onAdvancedScanChange: ((value: boolean) => void) | undefined,
  disabled: boolean,
) {
  if (!onAdvancedScanChange) return null;
  return (
    <div
      data-role="advanced-scan"
      className="tactile-card mt-3 flex items-center gap-3 rounded-lg border border-outline-variant/20 bg-surface-container-lowest px-3 py-2.5"
    >
      <span className="min-w-0 flex-1">
        <span className="block text-label-md font-label font-semibold text-on-surface leading-tight">
          Advanced scan
        </span>
        <span className="mt-0.5 block text-body-sm text-on-surface-variant leading-snug">
          The model thinks through the posting before answering, for a more
          careful read. It might take a few minutes.
        </span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={advancedScan}
        aria-label="Advanced scan"
        disabled={disabled}
        data-role="advanced-switch"
        onClick={() => onAdvancedScanChange(!advancedScan)}
        className={`relative h-6 w-10 shrink-0 rounded-full transition-all duration-200 active:scale-95 ${
          disabled ? 'opacity-60' : 'cursor-pointer'
        } ${
          advancedScan ? 'bg-secondary' : 'bg-surface-container-highest'
        }`}
      >
        <span
          aria-hidden
          className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full transition-transform duration-200 ${
            advancedScan ? 'translate-x-4 bg-on-secondary' : 'translate-x-0 bg-outline'
          }`}
        />
      </button>
    </div>
  );
}
export default ScanActions;
