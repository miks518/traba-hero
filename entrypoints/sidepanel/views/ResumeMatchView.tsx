import React, { useState, useCallback, useMemo } from 'react';
import { ResumePreview, JobMatchList, ResumeUploader } from '../components/match';
import { RedFlagCard } from '../components/scan';
import { ConfirmDialog, Icon, ToastContainer, useToastManager } from '../components/common';
import { analyzeResumeStream, matchResumeToJobsStream } from '../lib/api';
import type { ScanProgress } from '../lib/api';
import type { ScannedJob, ResumeData, JobMatchItem, IconName, JobFilterCategory } from '../types';

export interface ResumeMatchViewProps {
  scannedJobs: ScannedJob[];
  resumeData: ResumeData | null;
  onResumeData: (data: ResumeData) => void;
  onClearResume: () => void;
  onClearJobs: () => void;
  onProgressChange?: (progress: ScanProgress | null) => void;
  isOnline?: boolean;
}

const JOB_ICONS: IconName[] = ['work', 'architecture', 'database', 'shield_person', 'search', 'handshake'];

function jobIcon(index: number): IconName {
  return JOB_ICONS[index % JOB_ICONS.length];
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${d.getFullYear()}-${month}-${day} ${hours}:${minutes}`;
  } catch {
    return iso;
  }
}

function riskColor(score: number): string {
  if (score >= 70) return 'text-red-500';
  if (score >= 40) return 'text-amber-500';
  return 'text-green-500';
}

function riskLevelLabel(level: string | null | undefined): string {
  switch (level) {
    case 'low': return 'Low Risk';
    case 'moderate': return 'Moderate Risk';
    case 'high': return 'High Risk';
    case 'critical': return 'Critical Risk';
    default: return 'Not Scored';
  }
}

function matchBadgeStyle(score: number): string {
  if (score >= 76) return 'bg-red-900/30 text-red-400 border-red-500/40';
  if (score >= 46) return 'bg-orange-900/30 text-orange-400 border-orange-500/40';
  if (score >= 16) return 'bg-amber-900/30 text-amber-400 border-amber-500/40';
  return 'bg-green-900/30 text-green-400 border-green-500/40';
}

function isVerifiedJob(job: ScannedJob): boolean {
  return job.scanResult.riskLevel === 'low' && job.scanResult.isJobPosting;
}

function isSuspiciousJob(job: ScannedJob): boolean {
  return job.scanResult.riskLevel === 'moderate';
}

function isRiskyJob(job: ScannedJob): boolean {
  return job.scanResult.riskLevel === 'high' || job.scanResult.riskLevel === 'critical';
}

/** Scanned but never scored by external verification, so it cannot be matched. */
function isUnverifiedJob(job: ScannedJob): boolean {
  return job.scanResult.riskLevel === null;
}

export function ResumeMatchView({
  scannedJobs,
  resumeData,
  onResumeData,
  onClearResume,
  onClearJobs,
  onProgressChange,
  isOnline = true,
}: ResumeMatchViewProps) {
  const [analyzing, setAnalyzing] = useState(false);
  const [matching, setMatching] = useState(false);
  const [matches, setMatches] = useState<JobMatchItem[]>([]);
  const [matchScores, setMatchScores] = useState<Record<string, number>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [showUploadConfirm, setShowUploadConfirm] = useState(false);
  const [pendingResumeFile, setPendingResumeFile] = useState<{
    base64: string;
    fileType: string;
    fileName: string;
  } | null>(null);
  const [filterCategory, setFilterCategory] = useState<JobFilterCategory>('all');
  const [resumeProgress, setResumeProgress] = useState<ScanProgress | null>(null);
  const [matchProgress, setMatchProgress] = useState<ScanProgress | null>(null);
  const abortRef = React.useRef<AbortController | null>(null);
  const { toasts, showToast, removeToast } = useToastManager();

  const verifiedJobs = useMemo(() => scannedJobs.filter(isVerifiedJob), [scannedJobs]);
  const suspiciousJobs = useMemo(() => scannedJobs.filter(isSuspiciousJob), [scannedJobs]);
  const riskyJobs = useMemo(() => scannedJobs.filter(isRiskyJob), [scannedJobs]);
  const unverifiedJobs = useMemo(() => scannedJobs.filter(isUnverifiedJob), [scannedJobs]);

  const filteredJobs = useMemo(() => {
    if (filterCategory === 'verified') return verifiedJobs;
    if (filterCategory === 'suspicious') return suspiciousJobs;
    if (filterCategory === 'risky') return riskyJobs;
    return scannedJobs;
  }, [filterCategory, verifiedJobs, suspiciousJobs, riskyJobs, scannedJobs]);

  const processResumeFile = useCallback(async (base64: string, fileType: string, _fileName: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setAnalyzing(true);
    setResumeProgress({ percent: 5, stage: 'Preparing request' });
    onProgressChange?.({ percent: 5, stage: 'Preparing request' });
    try {
      const result = await analyzeResumeStream(
        base64,
        fileType,
        controller.signal,
        (p) => {
          setResumeProgress(p);
          onProgressChange?.(p);
        },
      );
      if (result.timedOut) {
        showToast('The analysis took too long. Please try again.', 'error');
        return;
      }
      if (result.data) {
        onResumeData(result.data);
        setMatches([]);
        setMatchScores({});
        showToast('Resume analyzed successfully', 'success');
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      showToast('There seems to be an error with our servers. Please try again later.', 'error');
    } finally {
      setAnalyzing(false);
      setResumeProgress(null);
      onProgressChange?.(null);
      setPendingResumeFile(null);
    }
  }, [onResumeData, showToast, onProgressChange]);

  const handleFileSelected = useCallback((base64: string, fileType: string, fileName: string) => {
    if (!isOnline) {
      showToast('Server unreachable. Check your connection and try again.', 'error');
      return;
    }
    setPendingResumeFile({ base64, fileType, fileName });
    setShowUploadConfirm(true);
  }, [isOnline, showToast]);

  const handleConfirmUpload = useCallback(() => {
    if (!pendingResumeFile) return;
    setShowUploadConfirm(false);
    processResumeFile(pendingResumeFile.base64, pendingResumeFile.fileType, pendingResumeFile.fileName);
  }, [pendingResumeFile, processResumeFile]);

  const handleCancelUpload = useCallback(() => {
    setShowUploadConfirm(false);
    setPendingResumeFile(null);
  }, []);

  const handleRunMatch = useCallback(async () => {
    if (!resumeData || verifiedJobs.length === 0) return;
    if (!isOnline) {
      showToast('Server unreachable. Check your connection and try again.', 'error');
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setMatching(true);
    setMatchProgress({ percent: 5, stage: 'Preparing request' });
    onProgressChange?.({ percent: 5, stage: 'Preparing request' });
    try {
      const result = await matchResumeToJobsStream(
        resumeData,
        verifiedJobs,
        controller.signal,
        (p) => {
          setMatchProgress(p);
          onProgressChange?.(p);
        },
      );
      if (result.timedOut) {
        showToast('The matching took too long. Please try again.', 'error');
        return;
      }
      if (result.data) {
        const mapped = (result.data.matches || []).map((m) => ({
          jobId: m.job_id,
          score: m.score ?? 0,
          label: m.label ?? '',
          skillGaps: m.skill_gaps ?? [],
          matchedSkills: m.matched_skills ?? [],
          reasoning: m.reasoning ?? '',
          experienceFit: m.experience_fit ?? '',
          industryFit: m.industry_fit ?? '',
          recommendedActions: m.recommended_actions ?? [],
        }));
        setMatches(mapped);
        setMatchScores(
          Object.fromEntries(mapped.map((m) => [m.jobId, m.score]))
        );
        showToast(`Matched against ${verifiedJobs.length} verified job${verifiedJobs.length !== 1 ? 's' : ''}`, 'success');
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      showToast('Match request failed. Please try again later.', 'error');
    } finally {
      setMatching(false);
      setMatchProgress(null);
      onProgressChange?.(null);
    }
  }, [resumeData, verifiedJobs, showToast, onProgressChange, isOnline]);

  const hasResume = resumeData !== null;
  const hasJobs = scannedJobs.length > 0;

  return (
    <div className="p-container-padding bg-background flex flex-col gap-stack-md relative">
      <ToastContainer toasts={toasts} onRemove={removeToast} />
      {(analyzing || matching) && (
        <div className="absolute top-0 left-0 w-full h-1 bg-surface-container-highest overflow-hidden rounded-full z-10">
          {(resumeProgress || matchProgress) ? (
            <div
              className="h-full bg-secondary rounded-full transition-all duration-300"
              style={{ width: `${(resumeProgress || matchProgress)?.percent ?? 0}%` }}
            />
          ) : (
            <div className="w-full h-full bg-secondary animate-loading-bar rounded-full" />
          )}
        </div>
      )}

      {riskyJobs.length > 0 && (
        <div className="flex items-start gap-3 p-3 rounded-xl bg-error-container/15 border border-error/30">
          <Icon name="shield_person" className="text-error mt-0.5 shrink-0" />
          <div className="flex flex-col gap-1">
            <p className="text-label-md font-bold text-error">High-Risk Postings Excluded</p>
            <p className="text-body-xs text-on-surface-variant">
              {riskyJobs.length} scanned job{riskyJobs.length !== 1 ? 's' : ''} scored high or critical risk after verification. They are in the <span className="font-bold text-on-surface">Critical/High Risk</span> category and are not used for resume matching.
            </p>
          </div>
        </div>
      )}

      {riskyJobs.length === 0 && suspiciousJobs.length > 0 && (
        <div className="flex items-start gap-3 p-3 rounded-xl bg-secondary-container/15 border border-secondary/30">
          <Icon name="warning" className="text-secondary mt-0.5 shrink-0" />
          <div className="flex flex-col gap-1">
<p className="text-label-md font-bold text-secondary">Moderate-Risk Postings Excluded</p>
             <p className="text-body-xs text-on-surface-variant">
               {suspiciousJobs.length} scanned job{suspiciousJobs.length !== 1 ? 's' : ''} scored moderate risk. They are in the <span className="font-bold text-on-surface">Moderate Risk</span> category and are not used for resume matching.
            </p>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Icon name="history" className="text-lg text-secondary" />
          <h2 className="text-headline-sm font-headline text-on-surface">Job Post History</h2>
        </div>
        <p className="text-body-sm text-on-surface-variant">
          Track your recently scanned career opportunities.
        </p>

        {scannedJobs.length > 0 && (
          <div className="flex items-center gap-1 p-1 bg-surface-container-low rounded-xl border border-outline-variant/20 mt-1">
            <button
              onClick={() => setFilterCategory('all')}
              title="All jobs"
              className={`relative flex-1 flex items-center justify-center py-2 rounded-lg transition-all ${
                filterCategory === 'all'
                  ? 'bg-surface-container-high text-on-surface shadow-sm'
                  : 'text-on-surface-variant hover:bg-surface-container'
              }`}
            >
              <Icon name="work" className="text-[1.25rem]" />
              <span className="absolute -top-0.5 -right-0.5 min-w-[1rem] h-[1rem] flex items-center justify-center px-0.5 rounded-full text-[0.5rem] font-bold bg-surface-container-highest text-on-surface-variant">
                {scannedJobs.length}
              </span>
            </button>

            <button
              onClick={() => setFilterCategory('verified')}
              title="Low Risk jobs"
              className={`relative flex-1 flex items-center justify-center py-2 rounded-lg transition-all ${
                filterCategory === 'verified'
                  ? 'bg-green-950/40 text-green-400 border border-green-500/40 shadow-sm'
                  : 'text-green-500 hover:bg-surface-container'
              }`}
            >
              <Icon name="verified" className="text-[1.25rem]" />
              {verifiedJobs.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[1rem] h-[1rem] flex items-center justify-center px-0.5 rounded-full text-[0.5rem] font-bold bg-green-900/40 text-green-300">
                  {verifiedJobs.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setFilterCategory('suspicious')}
              title="Moderate Risk jobs"
              className={`relative flex-1 flex items-center justify-center py-2 rounded-lg transition-all ${
                filterCategory === 'suspicious'
                  ? 'bg-amber-950/40 text-amber-400 border border-amber-500/40 shadow-sm'
                  : 'text-amber-500 hover:bg-surface-container'
              }`}
            >
              <Icon name="warning" className="text-[1.25rem]" />
              {suspiciousJobs.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[1rem] h-[1rem] flex items-center justify-center px-0.5 rounded-full text-[0.5rem] font-bold bg-amber-900/40 text-amber-300">
                  {suspiciousJobs.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setFilterCategory('risky')}
              title="High/Critical Risk jobs"
              className={`relative flex-1 flex items-center justify-center py-2 rounded-lg transition-all ${
                filterCategory === 'risky'
                  ? 'bg-red-950/40 text-red-400 border border-red-500/40 shadow-sm'
                  : 'text-red-500 hover:bg-surface-container'
              }`}
            >
              <Icon name="shield_person" className="text-[1.25rem]" />
              {riskyJobs.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[1rem] h-[1rem] flex items-center justify-center px-0.5 rounded-full text-[0.5rem] font-bold bg-red-900/40 text-red-300">
                  {riskyJobs.length}
                </span>
              )}
            </button>
          </div>
        )}
      </div>

      {filteredJobs.length > 0 && (
        <div className="flex flex-col gap-2">
          {[...filteredJobs].reverse().map((job, idx) => {
            const isExpanded = expandedId === job.id;
            const score = matchScores[job.id];
            const sr = job.scanResult;
            const verified = isVerifiedJob(job);
            const suspicious = isSuspiciousJob(job);
            return (
              <div key={job.id} className="flex flex-col">
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => setExpandedId(isExpanded ? null : job.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setExpandedId(isExpanded ? null : job.id);
                    }
                  }}
                  className="flex items-center gap-3 p-3 bg-surface-container-low border border-outline-variant/20 rounded-xl hover:bg-surface-container-high transition-colors cursor-pointer"
                >
                  <div className="w-10 h-10 rounded-lg bg-secondary-container/20 flex items-center justify-center shrink-0">
                    <Icon name={jobIcon(scannedJobs.length - 1 - idx)} className="text-lg text-secondary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="block text-body-md text-on-surface truncate">
                      {job.title || 'Scanned Job'}
                    </span>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="block text-label-sm text-on-surface-variant/70 truncate">
                        {job.timestamp ? formatTimestamp(job.timestamp) : ''}
                      </span>
                      {verified && (
                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[10px] bg-green-950/30 text-green-400 border border-green-500/30 font-medium shrink-0">
                          <Icon name="verified" className="text-[10px]" />
                          Low Risk
                        </span>
                      )}
                      {sr.riskLevel === null && (
                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[10px] bg-surface-container-high text-on-surface-variant border border-outline-variant/30 shrink-0 font-medium">
                          <Icon name="info" className="text-[10px]" />
                          Unverified
                        </span>
                      )}
                      {sr.riskLevel === 'critical' && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[10px] bg-error-container/20 text-error border border-error/30 shrink-0 font-medium">
                            <Icon name="shield_person" className="text-[10px]" />
                            Critical
                          </span>
                        )}
                        {sr.riskLevel === 'high' && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[10px] bg-amber-950/30 text-amber-400 border border-amber-500/30 shrink-0 font-medium">
                            <Icon name="warning" className="text-[10px]" />
                            High
                          </span>
                        )}
                        {suspicious && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[10px] bg-amber-950/30 text-amber-400 border border-amber-500/30 shrink-0 font-medium">
                            <Icon name="warning" className="text-[10px]" />
                            Moderate
                          </span>
                        )}
                    </div>
                  </div>
                  {score !== undefined && (
                    <span className={`px-2 py-0.5 rounded-full border text-label-md font-bold shrink-0 ${matchBadgeStyle(score)}`}>
                      {score}%
                    </span>
                  )}
                  <Icon
                    name={isExpanded ? 'keyboard_arrow_down' : 'chevron_right'}
                    className="text-lg text-on-surface-variant/40 shrink-0"
                  />
                </div>

                {isExpanded && sr && (
                  <div className="mx-2 px-3 py-3 bg-surface-container-low border border-outline-variant/10 border-t-0 rounded-b-xl flex flex-col gap-3 animate-slide-in">
                    {suspicious ? (
                      <div className="flex items-center gap-2 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-label-sm">
                        <Icon name="lock" className="text-xs shrink-0 text-amber-400" />
                        <span>Excluded from resume matching.</span>
                      </div>
                    ) : sr.riskLevel === null ? (
                      <div className="flex items-center gap-2 p-2 rounded-lg bg-surface-container border border-outline-variant/20 text-on-surface-variant text-label-sm">
                        <Icon name="info" className="text-xs shrink-0" />
                        <span>Not yet scored. Excluded from resume matching until external verification completes.</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 p-2 rounded-lg bg-green-500/10 border border-green-500/20 text-green-300 text-label-sm">
                        <Icon name="verified" className="text-xs shrink-0 text-green-400" />
                        <span>No high-severity indicators found. Included in resume matching.</span>
                      </div>
                    )}

                    {sr.riskScored && sr.riskScore !== null && (
                      <div className="flex items-center justify-between">
                        <span className="font-label-md text-on-surface-variant">
                          {sr.riskScore}% Risk
                        </span>
                        <span className={`font-label-md font-bold ${riskColor(sr.riskScore)}`}>
                          {riskLevelLabel(sr.riskLevel)}
                        </span>
                      </div>
                    )}

                    {job.summary && (
                      <div className="flex flex-col gap-1">
                        <span className="text-label-sm text-on-surface-variant uppercase tracking-wider text-[10px]">
                          Summary
                        </span>
                        <p className="text-body-sm text-on-surface/80 leading-relaxed">
                          {job.summary}
                        </p>
                      </div>
                    )}

                    {sr.riskDescription && (
                      <div className="flex flex-col gap-1">
                        <span className="text-label-sm text-on-surface-variant uppercase tracking-wider text-[10px]">
                          Analysis
                        </span>
                        <p className="text-body-sm text-on-surface-variant leading-relaxed">
                          {sr.riskDescription}
                        </p>
                      </div>
                    )}

                    {!sr.isJobPosting ? (
                      <p className="text-body-sm text-on-surface-variant/70 italic">
                        This wasn't detected as a job posting.
                      </p>
                    ) : sr.redFlags.length > 0 ? (
                      <div className="flex flex-col gap-1.5">
                        <span className="text-label-sm text-on-surface-variant uppercase tracking-wider text-[10px]">
                          Red Flags ({sr.redFlags.length})
                        </span>
                        {sr.redFlags.map((flag) => (
                          <RedFlagCard key={flag.id} flag={flag} />
                        ))}
                      </div>
                    ) : (
                      <p className="text-body-sm text-green-500/90">
                        No significant red flags detected.
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {scannedJobs.length === 0 && (
        <div className="text-center py-6 text-body-sm text-on-surface-variant bg-surface-container-low rounded-xl border border-outline-variant/10">
          <p>No jobs scanned yet. Go to the Scan tab to get started.</p>
        </div>
      )}

      {scannedJobs.length > 0 && filteredJobs.length === 0 && (
        <div className="text-center py-6 px-4 text-body-sm text-on-surface-variant bg-surface-container-low rounded-xl border border-outline-variant/10 flex flex-col items-center gap-1.5">
          {filterCategory === 'verified' && (
            <>
              <Icon name="verified" className="text-xl text-on-surface-variant/60" />
              <p className="font-medium text-on-surface">No low-risk jobs found</p>
              <p className="text-label-sm text-on-surface-variant/70">
                Only jobs that scored low risk after verification appear here.
              </p>
            </>
          )}
          {filterCategory === 'suspicious' && (
            <>
              <Icon name="check_circle" className="text-xl text-green-400" />
              <p className="font-medium text-on-surface">No moderate-risk jobs</p>
              <p className="text-label-sm text-on-surface-variant/70">
                No scanned posting scored moderate risk.
              </p>
            </>
          )}
          {filterCategory === 'risky' && (
            <>
              <Icon name="check_circle" className="text-xl text-green-400" />
              <p className="font-medium text-on-surface">No high-risk jobs</p>
              <p className="text-label-sm text-on-surface-variant/70">
                No scanned posting scored high or critical risk.
              </p>
            </>
          )}
        </div>
      )}

      <div className="border-t border-outline-variant/10 pt-3">
        {!hasResume ? (
          <div className="flex flex-col gap-3">
            <ResumeUploader onFileSelected={handleFileSelected} disabled={analyzing || !isOnline} />
            {analyzing && (
              <div className="flex items-center gap-2 text-on-surface-variant text-body-sm">
                <span className="w-2 h-2 rounded-full bg-secondary animate-ping" />
                <span>Analyzing… {resumeProgress?.percent ?? 0}%</span>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <ResumePreview
              data={resumeData}
              onRemove={onClearResume}
            />

            {hasJobs && !matching && (
              <div className="flex flex-col gap-2">
                <button
                  onClick={handleRunMatch}
                  disabled={matching || verifiedJobs.length === 0 || !isOnline}
                  title={isOnline ? undefined : 'Server unreachable'}
                  className="w-full tactile-btn-gold py-3 rounded-lg font-headline-md text-base flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed active:translate-y-[1px]"
                >
                  <Icon name="handshake" />
{matches.length > 0 ? 'Re-Match' : 'Match'}
                   {verifiedJobs.length > 0 ? ` (${verifiedJobs.length} Low Risk)` : ''}
                </button>
                {!isOnline && (
                  <p className="text-label-sm text-error text-center flex items-center justify-center gap-1">
                    <Icon name="cloud_off" className="text-xs shrink-0" />
                    Server unreachable. Matching is paused.
                  </p>
                )}
                {verifiedJobs.length === 0 && (
                  <p className="text-label-sm text-on-surface-variant text-center flex items-center justify-center gap-1">
                    <Icon name="info" className="text-xs shrink-0" />
                    No low-risk jobs available. {unverifiedJobs.length > 0 && `${unverifiedJobs.length} unverified. `}Moderate, high, and critical risk postings are not used for matching.
                  </p>
                )}
                {suspiciousJobs.length > 0 && verifiedJobs.length > 0 && (
                  <p className="text-label-sm text-on-surface-variant/80 text-center">
                    Matching against {verifiedJobs.length} low risk job{verifiedJobs.length !== 1 ? 's' : ''}. {suspiciousJobs.length} moderate risk job{suspiciousJobs.length !== 1 ? 's' : ''} excluded.
                  </p>
                )}
              </div>
            )}

            {matching && (
              <div className="flex items-center gap-2 text-on-surface-variant text-body-sm">
                <span className="w-2 h-2 rounded-full bg-secondary animate-ping" />
                <span>Matching… {matchProgress?.percent ?? 0}%</span>
              </div>
            )}
          </div>
        )}
      </div>

      {matches.length > 0 && (
        <JobMatchList jobs={verifiedJobs} matches={matches} />
      )}

      <div className="flex gap-2">
        {scannedJobs.length > 0 && (
          <button
            onClick={() => setShowClearConfirm(true)}
            className="px-3 py-1.5 rounded-lg border border-outline-variant/30 text-on-surface-variant hover:text-error hover:border-error/50 transition-colors text-label-md flex items-center gap-1"
          >
            <Icon name="delete" className="text-sm" />
            Clear History
          </button>
        )}
      </div>

      <ConfirmDialog
        open={showClearConfirm}
        title="Clear All Jobs"
        message="This will delete all scanned jobs and match results. Your resume data will be kept. Are you sure?"
        confirmLabel="Clear All"
        onConfirm={() => {
          onClearJobs();
          setMatches([]);
          setMatchScores({});
          setExpandedId(null);
          setShowClearConfirm(false);
        }}
        onCancel={() => setShowClearConfirm(false)}
      />

      <ConfirmDialog
        open={showUploadConfirm}
        title="Upload & Scan Resume?"
        message={`Are you sure you want to upload "${pendingResumeFile?.fileName || 'your resume'}"? It will be processed and scanned by AI to extract your skills, experience, and education for job matching.`}
        confirmLabel="Proceed & Scan"
        cancelLabel="Cancel"
        variant="primary"
        onConfirm={handleConfirmUpload}
        onCancel={handleCancelUpload}
      />
    </div>
  );
}

export default ResumeMatchView;
