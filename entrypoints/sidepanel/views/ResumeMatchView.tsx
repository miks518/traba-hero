import React, { useState, useCallback, useMemo } from 'react';
import { ResumePreview, JobMatchList, ResumeUploader } from '../components/match';
import { AnomalyCard } from '../components/scan';
import { ConfirmDialog, Icon, ToastContainer, useToastManager } from '../components/common';
import { analyzeResumeStream, matchResumeToJobsStream } from '../lib/api';
import type { ScanProgress } from '../lib/api';
import { formatTimestamp } from '../lib/format';
import { MAX_SCAN_HISTORY } from '../lib/scanHistory';
import type { ScannedJob, ResumeData, JobMatchItem, IconName, JobFilterCategory } from '../types';

export interface ResumeMatchViewProps {
  scannedJobs: ScannedJob[];
  resumeData: ResumeData | null;
  onResumeData: (data: ResumeData) => void;
  onClearResume: () => void;
  onClearJobs: () => void;
  onProgressChange?: (progress: ScanProgress | null) => void;
  isOnline?: boolean;
  /**
   * Open a scan from history. The panel it restores into lives in another view,
   * so this reports which job and nothing more — it does not navigate.
   */
  onOpenJob?: (job: ScannedJob) => void;
}

const JOB_ICONS: IconName[] = ['work', 'architecture', 'database', 'shield_person', 'search', 'handshake'];

function jobIcon(index: number): IconName {
  return JOB_ICONS[index % JOB_ICONS.length];
}



function assessmentLabel(assessment: string | null | undefined): string {
  switch (assessment) {
    case 'stop': return 'Do not proceed';
    case 'caution': return 'Caution';
    case 'note': return 'Note';
    case 'clear': return 'Proceed';
    default: return 'Not Assessed';
  }
}

/**
 * The assessment badge's chip class, one per assessment family.
 *
 * The status chips are the themed pair — pale fill, saturated ink, resolved per
 * theme — which is why this reads `chip-*` rather than a raw palette class. The
 * raw palette was authored for the dark theme (`green-400` on `green-900/30`)
 * and in light mode put pale text on a pale fill: "Proceed" was near-invisible.
 *
 * `note` shares the verified chip with `clear` on purpose. The report panel
 * gives both the verified tone (`assessmentCopy.ts`: the employer is confirmed in
 * both), so the history badge agrees with the banner it summarises, and the
 * label text is what tells them apart.
 */
function matchBadgeStyle(assessment: string | null | undefined): string {
  switch (assessment) {
    case 'stop': return 'chip-critical';
    case 'caution': return 'chip-caution';
    case 'note': return 'chip-verified';
    case 'clear': return 'chip-verified';
    default: return 'chip-stale';
  }
}

/**
 * A posting the reader can act on, so it is the set that gets matched.
 *
 * `clear` asks for nothing the rules prohibit. `note` asks for something
 * prohibited at an employer the record *confirmed*, which is why the reader can
 * go and see the fee on the employer's own site. Neither is a reason to withhold
 * the matching; `caution` and `stop` are.
 */
function isMatchableJob(job: ScannedJob): boolean {
  return (
    (job.scanResult.assessment === 'clear' || job.scanResult.assessment === 'note') &&
    job.scanResult.isJobPosting
  );
}

/** Caution or stop: the reader is being told to settle something first. */
function isExcludedJob(job: ScannedJob): boolean {
  return job.scanResult.assessment === 'caution' || job.scanResult.assessment === 'stop';
}

/** Scanned but never assessed by external verification, so it cannot be matched. */
function isUnassessedJob(job: ScannedJob): boolean {
  return job.scanResult.assessment === null;
}

/**
 * The history chips, one per assessment word.
 *
 * Each chip filters on the assessment itself, which is why there is no bucket
 * vocabulary left to drift: a chip reading "Caution" keeps exactly the rows
 * wearing a Caution badge.
 *
 * The colours are the theme-resolvable tokens (`assessment-*`, `chip-*`), not the
 * raw palette: an idle `text-green-500` read fine on the dark theme and washed
 * out on the light one, and the count badges had the same failure as the row
 * badges — pale ink on a pale fill. The active state takes the chip fill, so a
 * selected filter looks like the badges it selects.
 */
/** How each assessment is named in the empty-state sentence, where a sentence needs it. */
const FILTER_EMPTY_WORD: Record<Exclude<JobFilterCategory, 'all'>, string> = {
  clear: 'clear',
  note: 'a note',
  caution: 'a caution',
  stop: 'do not proceed',
};

const FILTER_CHIPS: {
  id: JobFilterCategory;
  title: string;
  icon: IconName;
  active: string;
  idle: string;
  badge: string;
}[] = [
  {
    id: 'all',
    title: 'All jobs',
    icon: 'work',
    active: 'bg-surface-container-high text-on-surface shadow-sm',
    idle: 'text-on-surface-variant hover:bg-surface-container',
    badge: 'bg-surface-container-highest text-on-surface-variant',
  },
  {
    id: 'clear',
    title: 'Proceed',
    icon: 'verified',
    active: 'chip-verified shadow-sm',
    idle: 'chip-verified',
    badge: 'chip-verified',
  },
  {
    id: 'note',
    title: 'Note',
    icon: 'warning',
    active: 'chip-verified shadow-sm',
    idle: 'chip-verified',
    badge: 'chip-verified',
  },
  {
    id: 'caution',
    title: 'Caution',
    icon: 'gpp_maybe',
    active: 'chip-caution shadow-sm',
    idle: 'chip-caution',
    badge: 'chip-caution',
  },
  {
    id: 'stop',
    title: 'Do not proceed',
    icon: 'shield_person',
    active: 'chip-critical shadow-sm',
    idle: 'chip-critical',
    badge: 'chip-critical',
  },
];

export function ResumeMatchView({
  scannedJobs,
  resumeData,
  onResumeData,
  onClearResume,
  onClearJobs,
  onProgressChange,
  isOnline = true,
  onOpenJob,
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

  const matchableJobs = useMemo(() => scannedJobs.filter(isMatchableJob), [scannedJobs]);
  const excludedJobs = useMemo(() => scannedJobs.filter(isExcludedJob), [scannedJobs]);
  const unassessedJobs = useMemo(() => scannedJobs.filter(isUnassessedJob), [scannedJobs]);

  /**
   * The filter reads the assessment directly, so a chip and the badge on the row it
   * keeps cannot disagree. It used to read three hand-rolled buckets, which is a
   * second definition of the same words.
   */
  const filteredJobs = useMemo(() => {
    if (filterCategory === 'all') return scannedJobs;
    return scannedJobs.filter((job) => job.scanResult.assessment === filterCategory);
  }, [filterCategory, scannedJobs]);

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
    if (!resumeData || matchableJobs.length === 0) return;
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
        matchableJobs,
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
        showToast(`Matched against ${matchableJobs.length} job${matchableJobs.length !== 1 ? 's' : ''}`, 'success');
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      showToast('Match request failed. Please try again later.', 'error');
    } finally {
      setMatching(false);
      setMatchProgress(null);
      onProgressChange?.(null);
    }
  }, [resumeData, matchableJobs, showToast, onProgressChange, isOnline]);

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

      {excludedJobs.length > 0 && (
        <div className="flex items-start gap-3 p-3 rounded-xl bg-error-container/15 border border-error/30">
          <Icon name="shield_person" className="text-error mt-0.5 shrink-0" />
          <div className="flex flex-col gap-1">
            <p className="text-label-md font-bold text-error">Postings Excluded From Matching</p>
            <p className="text-body-xs text-on-surface-variant">
              {excludedJobs.length} scanned job{excludedJobs.length !== 1 ? 's' : ''} came back{' '}
              <span className="font-bold text-on-surface">caution</span> or{' '}
              <span className="font-bold text-on-surface">do not proceed</span>, so they are
              not used for resume matching.
            </p>
          </div>
        </div>
      )}

      {/* The uploader sits above the history list so it can be reached without
          scrolling past every scan — twenty of them, now that there is a cap.
          Only the empty branch moved; see the note on the preview below. */}
      {!hasResume && (
        <div className="flex flex-col gap-3">
          <ResumeUploader onFileSelected={handleFileSelected} disabled={analyzing || !isOnline} />
          {analyzing && (
            <div className="flex items-center gap-2 text-on-surface-variant text-body-sm">
              <span className="w-2 h-2 rounded-full bg-secondary animate-ping" />
              <span>Analyzing… {resumeProgress?.percent ?? 0}%</span>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Icon name="history" className="text-lg text-secondary" />
          <h2 className="text-headline-sm font-headline text-on-surface">Job Post History</h2>
        </div>
        <p className="text-body-sm text-on-surface-variant">
          Your {MAX_SCAN_HISTORY} most recent scans are kept. When you scan another, the
          oldest one is deleted automatically.
        </p>

        {scannedJobs.length > 0 && (
          <div className="flex items-center gap-1 p-1 bg-surface-container-low rounded-xl border border-outline-variant/20 mt-1">
            {FILTER_CHIPS.map(({ id, title, icon, active, idle, badge }) => {
              const count =
                id === 'all'
                  ? scannedJobs.length
                  : scannedJobs.filter((job) => job.scanResult.assessment === id).length;
              return (
                <button
                  key={id}
                  onClick={() => setFilterCategory(id)}
                  title={title}
                  className={`relative flex-1 flex items-center justify-center py-2 rounded-lg transition-all ${
                    filterCategory === id ? active : idle
                  }`}
                >
                  <Icon name={icon} className="text-[1.25rem]" />
                  {count > 0 && (
                    <span
                      className={`absolute -top-0.5 -right-0.5 min-w-[1rem] h-[1rem] flex items-center justify-center px-0.5 rounded-full text-[0.5rem] font-bold ${badge}`}
                    >
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {filteredJobs.length > 0 && (
        <div className="flex flex-col gap-2">
          {[...filteredJobs].reverse().map((job, idx) => {
            const isExpanded = expandedId === job.id;
            const score = matchScores[job.id];
            const sr = job.scanResult;
            const excluded = isExcludedJob(job);
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
                      {sr.assessment === null ? (
                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[10px] chip-stale text-on-surface font-semibold shrink-0">
                          <Icon name="info" className="text-[10px]" />
                          Unverified
                        </span>
                      ) : (
                        <span
                          className={`inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[10px] font-semibold shrink-0 ${matchBadgeStyle(sr.assessment)}`}
                        >
                          <Icon
                            name={sr.assessment === 'clear' ? 'verified' : sr.assessment === 'stop' ? 'shield_person' : 'warning'}
                            className="text-[10px]"
                          />
                          {assessmentLabel(sr.assessment)}
                        </span>
                      )}
                      {sr.assessmentRecordedUnder === 'previous-procedure' && (
                        <span className="text-[10px] text-on-surface-variant/70 shrink-0">
                          under the previous procedure
                        </span>
                      )}
                    </div>
                  </div>
                  <Icon
                    name={isExpanded ? 'keyboard_arrow_down' : 'chevron_right'}
                    className="text-lg text-on-surface-variant/40 shrink-0"
                  />
                </div>

                {isExpanded && sr && (
                  <div className="mx-2 px-3 py-3 bg-surface-container-low border border-outline-variant/10 border-t-0 rounded-b-xl flex flex-col gap-3 animate-slide-in">
                    {/* Inside the expanded block and only there, so it cannot be
                        mistaken for a bulk action on the list, and so it is
                        offered for exactly the rows the reader opened. Gated on
                        `sr` with the rest of the block: an entry with no stored
                        result has nothing to reopen, and the button would open
                        an empty panel that reads like a clean scan. */}
                    {onOpenJob && (
                      <button
                        type="button"
                        data-role="open-job"
                        onClick={() => onOpenJob(job)}
                        className="tactile-btn-accent px-3 py-1.5 rounded-lg text-label-md flex items-center justify-center gap-1.5 self-start"
                      >
                        <Icon name="open_in_new" className="text-xs" />
                        Open scan
                      </button>
                    )}
                    {/* Three states, and each says which it is.
                        `caution` and `stop` are the excluded pair; `clear` and
                        `note` are matched. The chain used to test buckets that
                        no longer exist, which is how `high` and `critical` fell
                        through to "Included in resume matching" — the one branch
                        that must never be reassuring, taken by the most
                        dangerous posting. */}
                    {sr.assessment === null ? (
                      <div className="flex items-center gap-2 p-2 rounded-lg bg-surface-container border border-outline-variant/20 text-on-surface-variant text-label-sm">
                        <Icon name="info" className="text-xs shrink-0" />
                        <span>Not yet assessed. Excluded from resume matching until external verification completes.</span>
                      </div>
                    ) : excluded ? (
                      <div className="flex items-center gap-2 p-2 rounded-lg status-card-critical border text-assessment-critical text-label-sm">
                        <Icon name="shield_person" className="text-xs shrink-0" />
                        <span>Excluded from resume matching.</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 p-2 rounded-lg status-card-verified border text-assessment-verified text-label-sm">
                        <Icon name="verified" className="text-xs shrink-0" />
                        <span>Included in resume matching.</span>
                      </div>
                    )}

                    {sr.assessmentRecordedUnder === 'previous-procedure' && (
                      <p className="text-label-sm text-on-surface-variant">
                        This assessment wording was carried over from the previous
                        procedure, which recorded a level rather than a class of
                        request. Scan the posting again for a assessment this
                        version reached.
                      </p>
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
                    ) : sr.anomalies.length > 0 ? (
                      <div className="flex flex-col gap-1.5">
                        <span className="text-label-sm text-on-surface-variant uppercase tracking-wider text-[10px]">
                          Anomalies ({sr.anomalies.length})
                        </span>
                        {sr.anomalies.map((anomaly) => (
                          <AnomalyCard key={anomaly.id} anomaly={anomaly} />
                        ))}
                      </div>
                    ) : (
                      <p className="text-body-sm text-secondary">
                        No significant anomalies detected.
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
          {filterCategory !== 'all' && (
            <>
              <Icon name="check_circle" className="text-xl text-on-surface-variant/60" />
              <p className="font-medium text-on-surface">Nothing here yet</p>
              <p className="text-label-sm text-on-surface-variant/70">
                No scanned posting came back {FILTER_EMPTY_WORD[filterCategory]}.
              </p>
            </>
          )}
        </div>
      )}

      {/* Conditional on the wrapper, not just its contents: a bare bordered box
          renders as a stray divider line with nothing in it. */}
      {hasResume && (
        <div className="border-t border-outline-variant/10 pt-3">
          <div className="flex flex-col gap-3">
            <ResumePreview
              data={resumeData}
              onRemove={onClearResume}
            />

            {hasJobs && !matching && (
              <div className="flex flex-col gap-2">
                <button
                  onClick={handleRunMatch}
                  disabled={matching || matchableJobs.length === 0 || !isOnline}
                  title={isOnline ? undefined : 'Server unreachable'}
                  className="w-full tactile-btn-accent py-3 rounded-lg font-headline-md text-base flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed active:translate-y-[1px]"
                >
                  <Icon name="handshake" />
{matches.length > 0 ? 'Re-Match' : 'Match'}
                   {matchableJobs.length > 0 ? ` (${matchableJobs.length})` : ''}
                </button>
                {!isOnline && (
                  <p className="text-label-sm text-error text-center flex items-center justify-center gap-1">
                    <Icon name="cloud_off" className="text-xs shrink-0" />
                    Server unreachable. Matching is paused.
                  </p>
                )}
                {matchableJobs.length === 0 && (
                  <p className="text-label-sm text-on-surface-variant text-center flex items-center justify-center gap-1">
                    <Icon name="info" className="text-xs shrink-0" />
                    No proceed jobs available. {unassessedJobs.length > 0 && `${unassessedJobs.length} not yet assessed. `}Caution and do-not-proceed postings are not used for matching.
                  </p>
                )}
                {excludedJobs.length > 0 && matchableJobs.length > 0 && (
                  <p className="text-label-sm text-on-surface-variant/80 text-center">
                    Matching against {matchableJobs.length} job{matchableJobs.length !== 1 ? 's' : ''}. {excludedJobs.length} excluded.
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
        </div>
      )}

      {matches.length > 0 && (
        <JobMatchList jobs={matchableJobs} matches={matches} />
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
