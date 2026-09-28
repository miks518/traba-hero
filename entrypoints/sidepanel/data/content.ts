import type { NavTab } from '../types';

export const NAV_TABS: NavTab[] = [
  { id: 'scan', label: 'Scan', title: 'Scam Scan', icon: 'security' },
  { id: 'match', label: 'Match', title: 'Resume Match', icon: 'description' },
  // TEMPORARY debug tab for the web-search diagnostics. Remove with SearchDebugView.
  { id: 'search', label: 'Search', title: 'Search Debug', icon: 'search' },
];

export const BOTTOM_NAV_ICONS = ['close', 'contact_support'] as const;

export const FOOTER_LINKS = [
  { id: 'legal', label: 'Legal' },
  { id: 'privacy', label: 'Privacy' },
] as const;

export const FOOTER_COPYRIGHT = '\u00A9 2026 Trabahero';

export const RESCAN_LABEL = 'Re-scan Current Page';
export const RESCAN_BUSY_LABEL = 'Scanning...';

export const APPLY_LABEL = 'Apply with Match';
export const PICK_ELEMENT_LABEL = 'Pick a Job Post';
export const PICK_ELEMENT_ACTIVE_LABEL = 'Selecting...';
export const PICK_ELEMENT_CANCEL_LABEL = 'Cancel Selection';
export const PICK_AGAIN_LABEL = 'Pick again';
export const ELEMENT_SELECTED_LABEL = 'Post Selected';
