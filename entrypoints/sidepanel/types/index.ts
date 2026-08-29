export type ViewId = 'scan' | 'match' | 'test';

export type IconName =
  | 'security'
  | 'description'
  | 'help'
  | 'settings'
  | 'contact_support'
  | 'open_in_new'
  | 'warning'
  | 'bolt'
  | 'refresh'
  | 'flag'
  | 'alternate_email'
  | 'payments'
  | 'history_edu'
  | 'phone_disabled'
  | 'picture_as_pdf'
  | 'edit'
  | 'add'
  | 'check_circle'
  | 'rocket_launch'
  | 'close'
  | 'touch_app'
  | 'crop'
  | 'info'
  | 'upload_file'
  | 'delete'
  | 'work'
  | 'dark_mode'
  | 'light_mode'
  | 'smart_toy'
  | 'travel_explore'
  | 'chevron_left'
  | 'chevron_right'
  | 'keyboard_arrow_down'
  | 'history'
  | 'handshake'
  | 'search'
  | 'architecture'
  | 'database'
  | 'shield_person'
  | 'timer'
  | 'calendar_month'
  | 'lock';

export interface NavTab {
  id: ViewId;
  label: string;
  title: string;
  icon: IconName;
}

export interface RedFlag {
  id: string;
  title: string;
  description: string;
  icon: IconName;
}

export interface SkillGap {
  id: string;
  label: string;
}

export interface MatchKeyword {
  id: string;
  label: string;
  matched: boolean;
}

export interface ScanResult {
  status: 'scam' | 'suspicious' | 'legitimate';
  statusTitle: string;
  scanningTarget: string;
  riskScore: number;
  riskDescription: string;
  redFlags: RedFlag[];
  flagsCritical: boolean;
  isJobPosting: boolean;
}

export interface ScannedJob {
  id: string;
  title: string;
  summary: string;
  timestamp: string;
  scanResult: ScanResult;
}

export interface ResumeData {
  skills: string[];
  experience_years: number;
  job_titles: string[];
  industries: string[];
  summary: string;
}

export interface JobMatchItem {
  jobId: string;
  score: number;
  label: string;
  skillGaps: string[];
  matchedSkills: string[];
}

export interface MatchResult {
  resume: {
    filename: string;
    lastUpdated: string;
  };
  matchScore: number;
  compatibilityLabel: string;
  skillGaps: SkillGap[];
  topKeywords: MatchKeyword[];
  matches: JobMatchItem[];
}

export interface ApiErrorResponse {
  status: number;
  message: string;
  details?: string;
}

export type ApiStatus = 'idle' | 'loading' | 'success' | 'error';

export interface ApiScanResponse {
  valid: boolean;
  verdict_percentage: number;
  red_flags: { flag: string; reasoning: string; severity: string }[];
  analysis: string;
  job_summary: string;
  error?: string | null;
}
