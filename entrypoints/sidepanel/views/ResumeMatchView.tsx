import React, { useState, useCallback } from 'react';
import { ResumePreview, JobMatchList, ResumeUploader } from '../components/match';
import { RedFlagCard } from '../components/scan';
import { ConfirmDialog, Icon, ToastContainer, useToastManager } from '../components/common';
import { analyzeResume, matchResumeToJobs } from '../lib/api';
import type { ScannedJob, ResumeData, JobMatchItem, IconName } from '../types';

export interface ResumeMatchViewProps {
  scannedJobs: ScannedJob[];
  resumeData: ResumeData | null;
  onResumeData: (data: ResumeData) => void;
  onClearResume: () => void;
  onClearJobs: () => void;
  isLocked?: boolean;
  hasWarnings?: boolean;
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

function riskLabel(score: number): string {
  if (score >= 70) return 'Scam';
  if (score >= 40) return 'Suspicious';
  return 'Legitimate';
}

function matchBadgeStyle(score: number): string {
  if (score >= 70) return 'bg-green-900/30 text-green-400 border-green-500/40';
  if (score >= 40) return 'bg-amber-900/30 text-amber-400 border-amber-500/40';
  return 'bg-red-900/30 text-red-400 border-red-500/40';
}

export function ResumeMatchView({
  scannedJobs,
  resumeData,
  onResumeData,
  onClearResume,
  onClearJobs,
  isLocked = false,
  hasWarnings = false,
}: ResumeMatchViewProps) {
  const [analyzing, setAnalyzing] = useState(false);
  const [matching, setMatching] = useState(false);
  const [matches, setMatches] = useState<JobMatchItem[]>([]);
  const [matchScores, setMatchScores] = useState<Record<string, number>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [replacing, setReplacing] = useState(false);
  const { toasts, showToast, removeToast } = useToastManager();

  const handleFileSelected = useCallback(async (base64: string, fileType: string, _fileName: string) => {
    setAnalyzing(true);
    try {
      const data = await analyzeResume(base64, fileType);
      onResumeData(data);
      setMatches([]);
      setMatchScores({});
      showToast('Resume analyzed successfully', 'success');
    } catch (e) {
      showToast('There seems to be an error with our servers. Please try again later.', 'error');
    } finally {
      setAnalyzing(false);
      setReplacing(false);
    }
  }, [onResumeData, showToast]);

  const handleRunMatch = useCallback(async () => {
    if (!resumeData || scannedJobs.length === 0) return;
    setMatching(true);
    try {
      const result = await matchResumeToJobs(resumeData, scannedJobs);
      const mapped = (result.matches || []).map((m) => ({
        jobId: m.job_id,
        score: m.score,
        label: m.label,
        skillGaps: m.skill_gaps,
        matchedSkills: m.matched_skills,
        reasoning: m.reasoning,
        experienceFit: m.experience_fit,
        industryFit: m.industry_fit,
        recommendedActions: m.recommended_actions,
      }));
      setMatches(mapped);
      setMatchScores(
        Object.fromEntries(mapped.map((m) => [m.jobId, m.score]))
      );
      showToast(`Matched against ${scannedJobs.length} job${scannedJobs.length !== 1 ? 's' : ''}`, 'success');
    } catch (e) {
      showToast('Match request failed. Please try again later.', 'error');
    } finally {
      setMatching(false);
    }
  }, [resumeData, scannedJobs, showToast]);

  const hasResume = resumeData !== null;
  const hasJobs = scannedJobs.length > 0;
  const highRiskJobs = scannedJobs.filter((j) => j.scanResult.status === 'scam');
  const mediumRiskJobs = scannedJobs.filter((j) => j.scanResult.status === 'suspicious');

  if (isLocked) {
    return (
      <div className="p-container-padding bg-background flex flex-col gap-stack-md relative">
        <ToastContainer toasts={toasts} onRemove={removeToast} />

        <div className="flex items-start gap-3 p-3 rounded-xl bg-error-container/15 border border-error/30">
          <Icon name="lock" className="text-error mt-0.5 shrink-0" />
          <div className="flex flex-col gap-1">
            <p className="text-label-md font-bold text-error">Resume upload locked</p>
            <p className="text-body-xs text-on-surface-variant">
              {highRiskJobs.length} scanned job{highRiskJobs.length !== 1 ? 's' : ''} flagged as <span className="font-bold text-error">scam</span>. Uploading your resume to suspicious employers puts your personal data at risk.
            </p>
            <p className="text-body-xs text-on-surface-variant">
              Clear the flagged jobs or scan safer postings to unlock resume matching.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <h2 className="text-headline-sm font-headline text-on-surface">Resume Match</h2>
          <p className="text-body-sm text-on-surface-variant">
            Resume matching is disabled while scam jobs are in your scan list.
          </p>

          <div className="flex flex-col gap-2 mt-2">
            <p className="text-label-md text-on-surface-variant font-bold">Flagged jobs:</p>
            {highRiskJobs.map((job) => (
              <div key={job.id} className="flex items-center gap-2 p-2 rounded-lg bg-error-container/10 border border-error/20">
                <Icon name="warning" className="text-error text-sm shrink-0" />
                <span className="text-body-sm text-on-surface truncate">{job.title}</span>
                <span className="text-body-xs text-error ml-auto shrink-0">{job.scanResult.riskScore}%</span>
              </div>
            ))}
          </div>

          <button
            onClick={() => setShowClearConfirm(true)}
            className="mt-2 px-3 py-1.5 rounded-lg border border-outline-variant/30 text-on-surface-variant hover:text-error hover:border-error/50 transition-colors text-label-md flex items-center gap-1 self-start"
          >
            <Icon name="delete" className="text-sm" />
            Clear Flagged Jobs
          </button>
        </div>

        <ConfirmDialog
          open={showClearConfirm}
          title="Clear All Jobs"
          message="This will delete all scanned jobs and unlock resume matching. Are you sure?"
          confirmLabel="Clear All"
          onConfirm={() => {
            onClearJobs();
            setMatches([]);
            setShowClearConfirm(false);
          }}
          onCancel={() => setShowClearConfirm(false)}
        />
      </div>
    );
  }

  return (
    <div className="p-container-padding bg-background flex flex-col gap-stack-md relative">
      <ToastContainer toasts={toasts} onRemove={removeToast} />
      {(analyzing || matching) && (
        <div className="absolute top-0 left-0 w-full h-1 bg-surface-container-highest overflow-hidden rounded-full z-10">
          <div className="w-full h-full bg-secondary animate-loading-bar rounded-full" />
        </div>
      )}

      {hasWarnings && (
        <div className="flex items-start gap-3 p-3 rounded-xl bg-secondary-container/15 border border-secondary/30">
          <Icon name="warning" className="text-secondary mt-0.5 shrink-0" />
          <div className="flex flex-col gap-1">
            <p className="text-label-md font-bold text-secondary">Suspicious jobs detected</p>
            <p className="text-body-xs text-on-surface-variant">
              {mediumRiskJobs.length} scanned job{mediumRiskJobs.length !== 1 ? 's' : ''} flagged as <span className="font-bold text-secondary">suspicious</span>. Review these carefully before sharing your resume.
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
      </div>

      {scannedJobs.length > 0 && (
        <div className="flex flex-col gap-2">
          {[...scannedJobs].reverse().map((job, idx) => {
            const isExpanded = expandedId === job.id;
            const score = matchScores[job.id];
            const sr = job.scanResult;
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
                    <span className="block text-label-sm text-on-surface-variant/70 truncate">
                      {job.timestamp ? formatTimestamp(job.timestamp) : ''}
                    </span>
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
                    <div className="flex items-center justify-between">
                      <span className="font-label-md text-on-surface-variant">
                        {sr.riskScore}% Risk
                      </span>
                      <span className={`font-label-md font-bold ${riskColor(sr.riskScore)}`}>
                        {riskLabel(sr.riskScore)}
                      </span>
                    </div>

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

      <div className="border-t border-outline-variant/10 pt-3">
        {!hasResume || replacing ? (
          <div className="flex flex-col gap-3">
            <ResumeUploader onFileSelected={handleFileSelected} disabled={analyzing} />
            {analyzing && (
              <div className="flex items-center gap-2 text-on-surface-variant text-body-sm">
                <span className="inline-block w-3 h-3 border-2 border-secondary border-t-transparent rounded-full animate-spin" />
                Analyzing your resume...
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <ResumePreview
              data={resumeData}
              onReplace={() => setReplacing(true)}
              onRemove={onClearResume}
            />

            {hasJobs && !matching && (
              <button
                onClick={handleRunMatch}
                disabled={matching}
                className="w-full tactile-btn-gold py-3 rounded-lg font-headline-md text-base flex items-center justify-center gap-2 disabled:opacity-70 active:translate-y-[1px]"
              >
                <Icon name="handshake" />
                {matches.length > 0 ? 'Re-Match' : 'Match'}
              </button>
            )}

            {matching && (
              <div className="flex items-center gap-2 text-on-surface-variant text-body-sm">
                <span className="inline-block w-3 h-3 border-2 border-secondary border-t-transparent rounded-full animate-spin" />
                Matching your resume against {scannedJobs.length} job{scannedJobs.length !== 1 ? 's' : ''}...
              </div>
            )}
          </div>
        )}
      </div>

      {matches.length > 0 && (
        <JobMatchList jobs={scannedJobs} matches={matches} />
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
    </div>
  );
}

export default ResumeMatchView;
