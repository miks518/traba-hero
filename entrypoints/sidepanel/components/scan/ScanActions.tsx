import React from 'react';
import { Icon } from '../common/Icon';
import {
  PICK_ELEMENT_LABEL,
  PICK_ELEMENT_ACTIVE_LABEL,
  PICK_ELEMENT_CANCEL_LABEL,
  PICK_AGAIN_LABEL,
} from '../../data/content';

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
    <section className="flex flex-col gap-3">
      <button
        onClick={handlePickToggle}
        disabled={isPickerActivating}
        className={`w-full py-2.5 rounded-lg font-label-md flex items-center justify-center gap-2 transition-all active:translate-y-[1px] ${
          isPickerActive
            ? 'bg-error/20 text-error border border-error/30 hover:bg-error/30'
            : 'tactile-btn-gold py-3 rounded-lg font-headline-md text-base disabled:opacity-70'
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

      <button
        onClick={handleCropToggle}
        disabled={isCropActivating}
        className={`w-full py-2.5 rounded-lg font-label-md flex items-center justify-center gap-2 transition-all active:translate-y-[1px] ${
          isCropActive
            ? 'bg-error/20 text-error border border-error/30 hover:bg-error/30'
            : 'btn-outline-gold'
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
    </section>
  );
}

export default ScanActions;
