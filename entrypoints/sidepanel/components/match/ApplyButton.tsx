import React from 'react';
import { Icon } from '../common/Icon';
import { APPLY_LABEL } from '../../data/content';

export interface ApplyButtonProps {
  label?: string;
  onClick?: () => void;
}

export function ApplyButton({ label = APPLY_LABEL, onClick }: ApplyButtonProps) {
  return (
    <button
      onClick={onClick}
      className="w-full tactile-btn-accent py-3.5 px-4 rounded-xl font-headline-md text-base flex items-center justify-center gap-2 shadow-tactile-accent"
    >
      <Icon name="rocket_launch" />
      {label}
    </button>
  );
}

export default ApplyButton;
