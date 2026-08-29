import type { NavTab, RedFlag, SkillGap, MatchKeyword, ScanResult, MatchResult } from '../types';

export const NAV_TABS: NavTab[] = [
  { id: 'scan', label: 'Scan', title: 'Scam Scan', icon: 'security' },
  { id: 'match', label: 'Match', title: 'Resume Match', icon: 'description' },
  { id: 'test', label: 'Test', title: 'Model Test', icon: 'smart_toy' },
];

export const BOTTOM_NAV_ICONS = ['close', 'contact_support'] as const;

export const SCAN_RESULT_DEMO: ScanResult = {
  status: 'scam',
  statusTitle: 'Scam',
  scanningTarget: 'Senior Frontend Dev at \"Global-Tech\"',
  riskScore: 75,
  riskDescription: 'This listing matches high-frequency scam patterns observed in the last 48 hours.',
  flagsCritical: true,
  isJobPosting: true,
  redFlags: [
    {
      id: 'unprofessional-domain',
      title: 'Unprofessional Domain',
      description: 'Recruiter using @gmail.com or @outlook.com instead of verified corporate domain.',
      icon: 'alternate_email',
    },
    {
      id: 'vague-salary',
      title: 'Vague Salary Range',
      description: 'Listing mentions \" - \" without specific role requirements.',
      icon: 'payments',
    },
    {
      id: 'ai-content',
      title: 'AI Generated Content',
      description: 'High probability of job description being 100% synthetically generated.',
      icon: 'history_edu',
    },
    {
      id: 'suspicious-contact',
      title: 'Suspicious Contact Info',
      description: 'No physical address or verifiable company phone number provided.',
      icon: 'phone_disabled',
},
  ],
};

export const MATCH_RESULT_DEMO: MatchResult = {
  resume: {
    filename: 'Jordan_Doe_Resume_2024.pdf',
    lastUpdated: '2 days ago',
  },
  matchScore: 85,
  compatibilityLabel: 'High Compatibility',
  skillGaps: [
    { id: 'kubernetes', label: 'Kubernetes' },
    { id: 'graphql', label: 'GraphQL' },
    { id: 'agile-coaching', label: 'Agile Coaching' },
  ],
  topKeywords: [
    { id: 'system-architecture', label: 'System Architecture', matched: true },
    { id: 'cloud-infra', label: 'Cloud Infrastructure', matched: true },
    { id: 'cicd-pipelines', label: 'CI/CD Pipelines', matched: true },
  ],
  matches: [],
};

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
