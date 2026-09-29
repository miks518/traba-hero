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
    </div>
  );
}

export default ScanActions;
