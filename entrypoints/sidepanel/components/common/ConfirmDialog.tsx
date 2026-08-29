import React from 'react';
import { Icon } from './Icon';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-80 rounded-xl bg-surface-container-high border border-outline-variant/30 shadow-xl p-5 flex flex-col gap-4">
        <h3 className="text-headline-xs font-headline text-on-surface">{title}</h3>
        <p className="text-body-sm text-on-surface-variant">{message}</p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg border border-outline-variant/30 text-on-surface-variant hover:text-secondary hover:border-secondary/50 transition-colors text-label-md"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 rounded-lg bg-error/20 border border-error/30 text-error hover:bg-error/30 transition-colors text-label-md"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmDialog;
