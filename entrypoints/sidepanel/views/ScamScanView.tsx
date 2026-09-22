import React, { useState, useCallback, useEffect, useRef } from 'react';
import { RiskGauge, RedFlagsList, ScanActions, PickerButton, InvalidContentError } from '../components/scan';
import { Icon, ToastContainer, useToastManager } from '../components/common';
import { scanScreenshotStream, ApiRequestError, type ScanProgress } from '../lib/api';
import { compressImage } from '../lib/imageUtils';
import type { ScanResult, IconName, ScannedJob, ApiScanResponse } from '../types';

export interface ScamScanViewProps {
  onScanComplete?: (job: ScannedJob) => void;
  onScanProgressChange?: (progress: ScanProgress | null) => void;
}

const SEVERITY_ICONS: Record<string, IconName> = {
  low: 'info',
  mid: 'warning',
  high: 'warning',
};

let jobIdCounter = 0;

function mapApiResponse(data: ApiScanResponse): ScanResult {
  const isJobPosting = data.valid;
  const score = data.verdict_percentage ?? 50;
  const flags = data.red_flags ?? [];
  const hasCritical = flags.some((f) => f.severity === 'high');
  const flagCount = flags.length;

  let status: ScanResult['status'];
  let statusTitle: string;
  if (!isJobPosting) {
    status = 'legitimate';
    statusTitle = 'Not a Job Posting';
  } else if (hasCritical) {
    status = 'scam';
    statusTitle = 'Scam';
  } else if (flagCount >= 2) {
    status = 'scam';
    statusTitle = 'Scam';
  } else if (flagCount === 1) {
    status = 'suspicious';
    statusTitle = 'Suspicious';
  } else if (score >= 40) {
    status = 'suspicious';
    statusTitle = 'Suspicious';
  } else {
    status = 'legitimate';
    statusTitle = 'Legitimate';
  }
  return {
    status,
    statusTitle,
    scanningTarget: 'Scanned Element',
    riskScore: score,
    riskDescription: data.analysis || 'Analysis completed.',
    redFlags: (data.red_flags ?? []).map((f, i) => ({
      id: `flag-${i}`,
      title: f.flag,
      description: f.reasoning,
      icon: SEVERITY_ICONS[f.severity] || 'warning',
      severity: f.severity as 'low' | 'mid' | 'high',
    })),
    flagsCritical: hasCritical,
    isJobPosting,
    companyName: data.company_name || null,
    secRegistration: data.sec_registration || [],
    webSearch: data.web_search || {},
    jobSummary: data.job_summary || undefined,
    emailVerifications: (data.email_verifications ?? []).map((e) => ({
      email: e.email,
      domain: e.domain,
      syntaxValid: e.syntax_valid,
      hasMxRecords: e.has_mx_records,
      isDisposable: e.is_disposable,
      risk: e.risk,
      reason: e.reason,
    })),
    scoreBreakdown: data.score_breakdown || undefined,
    externalVerification: data.external_verification || undefined,
  };
}

export function ScamScanView({
  onScanComplete,
  onScanProgressChange,
}: ScamScanViewProps) {
  const [pickerPhase, setPickerPhase] = useState(0);
  const [pickerCancelPhase, setPickerCancelPhase] = useState(0);
  const [pickerActive, setPickerActive] = useState(false);
  const [pickerActivating, setPickerActivating] = useState(false);

  const [cropPhase, setCropPhase] = useState(0);
  const [cropCancelPhase, setCropCancelPhase] = useState(0);
  const [cropActive, setCropActive] = useState(false);
  const [cropActivating, setCropActivating] = useState(false);

  const MAX_SCREENSHOTS = 4;

  const [screenshots, setScreenshots] = useState<string[]>([]);
  const [hasSelection, setHasSelection] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [hasScanned, setHasScanned] = useState(false);
  const [isValidJob, setIsValidJob] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const [progress, setProgress] = useState<ScanProgress | null>(null);
  const progressPercent = progress?.percent ?? 0;

  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const { toasts, showToast, removeToast } = useToastManager();

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (lightboxIndex !== null) {
        setLightboxIndex(null);
        return;
      }
      if (pickerActive) {
        setPickerCancelPhase((p) => p + 1);
      } else if (cropActive) {
        setCropCancelPhase((p) => p + 1);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [pickerActive, cropActive, lightboxIndex]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const handleScreenshotReady = useCallback(async (dataUrl: string) => {
    const compressed = await compressImage(dataUrl);
    setScreenshots((prev) => {
      if (prev.length >= MAX_SCREENSHOTS) {
        showToast(`You can select up to ${MAX_SCREENSHOTS} images only. Remove one to add another.`, 'error');
        return prev;
      }
      return [...prev, compressed];
    });
  }, [showToast]);

  const removeScreenshot = useCallback((index: number) => {
    setScreenshots((prev) => {
      const next = prev.filter((_, i) => i !== index);
      if (next.length === 0) {
        setHasSelection(false);
        setHasScanned(false);
        setScanResult(null);
        setProgress(null);
        onScanProgressChange?.(null);
      }
      return next;
    });
  }, [onScanProgressChange]);

  const resetAll = useCallback(() => {
    setScreenshots([]);
    setHasScanned(false);
    setIsLoading(false);
    setHasSelection(false);
    setScanResult(null);
    setIsValidJob(false);
    setProgress(null);
    onScanProgressChange?.(null);
    setPickerCancelPhase((p) => p + 1);
  }, [onScanProgressChange]);

  const handlePickElement = useCallback(() => {
    if (isLoading) return;
    if (hasScanned) {
      resetAll();
    } else if (pickerActive) {
      setPickerCancelPhase((p) => p + 1);
    } else {
      setPickerPhase((p) => p + 1);
    }
  }, [isLoading, hasScanned, pickerActive, resetAll]);

  const handleSelectionChange = useCallback((selected: boolean) => {
    if (screenshots.length === 0) {
      setHasSelection(selected);
    }
    if (!selected) {
      setHasScanned(false);
      setIsLoading(false);
      setScanResult(null);
      setIsValidJob(false);
      setProgress(null);
      onScanProgressChange?.(null);
    }
  }, [screenshots.length, onScanProgressChange]);

  const handleScan = useCallback(async () => {
    if (screenshots.length === 0) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setProgress({ percent: 5, stage: 'Preparing request' });
    onScanProgressChange?.({ percent: 5, stage: 'Preparing request' });
    try {
      const result = await scanScreenshotStream(
        screenshots.map((s) => s.split(',')[1]),
        controller.signal,
        (p) => {
          setProgress(p);
          onScanProgressChange?.(p);
        },
      );
      if (result.timedOut) {
        showToast('The scan took too long. Check that the AI service is running.', 'error');
        setProgress(null);
        onScanProgressChange?.(null);
        return;
      }
      if (!result.response) {
        showToast('Scan ended before returning a result. Please try again.', 'error');
        setProgress(null);
        onScanProgressChange?.(null);
        return;
      }
      const data = result.response;
      const mapped = mapApiResponse(data);
      setScanResult(mapped);
      setHasScanned(true);
      setIsValidJob(mapped.isJobPosting);
      setProgress(null);
      onScanProgressChange?.(null);
      if (mapped.isJobPosting) {
        const jobTitle = data.job_summary
          ? data.job_summary.slice(0, 60).replace(/\s+\S*$/, '')
          : mapped.scanningTarget;
        onScanComplete?.({
          id: `job-${++jobIdCounter}`,
          title: jobTitle,
          summary: data.job_summary,
          timestamp: new Date().toISOString(),
          scanResult: mapped,
        });
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      setProgress(null);
      onScanProgressChange?.(null);
      showToast(friendlyError(e), 'error');
    } finally {
      setIsLoading(false);
    }
  }, [screenshots, showToast, onScanComplete, onScanProgressChange]);

  function friendlyError(e: unknown): string {
    if (e instanceof DOMException && e.name === 'AbortError') return 'The scan took too long. Check that the backend is running and try again.';
    if (e instanceof TypeError) return 'Could not connect to the AI service. Make sure the backend is running.';
    if (e instanceof ApiRequestError) {
      if (e.status === 502) return 'Hmm, I can\'t scan at the moment. Please try again.';
      if (e.status === 504) return 'The scan took too long. Check that the AI service is running.';
      if (e.status === 429) return 'Too many requests. Please wait a moment and try again.';
      if (e.status === 422) return 'The image could not be processed. Try selecting a different area.';
      if (e.status >= 500) return 'The AI service encountered an error. Please try again later.';
    }
    return 'Something went wrong during the scan. Please try again.';
  }

  return (
    <div className="p-container-padding pb-24 bg-background flex flex-col gap-stack-md relative">
      <ToastContainer toasts={toasts} onRemove={removeToast} />

      {isLoading && (
        <div className="absolute top-0 left-0 w-full h-1 bg-surface-container-highest overflow-hidden rounded-full">
          <div className="w-full h-full bg-secondary animate-loading-bar rounded-full" />
        </div>
      )}

      {!hasScanned && (
        <div className="flex flex-col gap-2">
          <h2 className="text-headline-sm font-headline text-on-surface">Scam Scan</h2>
          <p className="text-body-sm text-on-surface-variant">
            Pick a job post from the page to check for scam indicators.
          </p>
        </div>
      )}

      {hasScanned && scanResult && isValidJob && (
        <>
          <RiskGauge score={scanResult.riskScore} description={scanResult.riskDescription} status={scanResult.status} />

          {scanResult.scoreBreakdown && (scanResult.scoreBreakdown.high_count + scanResult.scoreBreakdown.mid_count + scanResult.scoreBreakdown.low_count) > 0 && (
            <div className="flex flex-col gap-2 p-4 rounded-xl bg-surface-container-low border border-outline-variant/20">
              <div className="flex items-center gap-2">
                <Icon name="architecture" className="text-secondary" />
                <h3 className="text-label-md font-bold text-on-surface">Score Calculation</h3>
              </div>
              <div className="flex flex-wrap gap-3 text-body-sm text-on-surface-variant">
                {scanResult.scoreBreakdown.high_count > 0 && (
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-error" />
                    {scanResult.scoreBreakdown.high_count} HIGH × {scanResult.scoreBreakdown.high_weight} = {scanResult.scoreBreakdown.high_count * scanResult.scoreBreakdown.high_weight}
                  </span>
                )}
                {scanResult.scoreBreakdown.mid_count > 0 && (
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-secondary" />
                    {scanResult.scoreBreakdown.mid_count} MID × {scanResult.scoreBreakdown.mid_weight} = {scanResult.scoreBreakdown.mid_count * scanResult.scoreBreakdown.mid_weight}
                  </span>
                )}
                {scanResult.scoreBreakdown.low_count > 0 && (
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-outline" />
                    {scanResult.scoreBreakdown.low_count} LOW × {scanResult.scoreBreakdown.low_weight} = {scanResult.scoreBreakdown.low_count * scanResult.scoreBreakdown.low_weight}
                  </span>
                )}
              </div>
              <span className="text-body-sm text-on-surface-variant font-mono break-all">
                {scanResult.scoreBreakdown.formula} → <span className="font-bold text-on-surface">{scanResult.scoreBreakdown.normalized_score}/100</span>
              </span>
            </div>
          )}

          {hasScanned && (
            <div className="flex flex-wrap gap-2">
              {screenshots.map((ss, i) => (
                <button
                  key={i}
                  onClick={() => setLightboxIndex(i)}
                  className="w-16 h-16 rounded-lg overflow-hidden border border-outline-variant/20 bg-surface-container shrink-0 hover:ring-2 hover:ring-secondary transition-all"
                >
                  <img src={ss} alt={`Screenshot ${i + 1}`} className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          )}

          <RedFlagsList flags={scanResult.redFlags} critical={scanResult.flagsCritical} />

          {scanResult.jobSummary && (
            <div className="flex flex-col gap-2 p-4 rounded-xl bg-surface-container-low border border-outline-variant/20">
              <div className="flex items-center gap-2">
                <Icon name="description" className="text-secondary" />
                <h3 className="text-label-md font-bold text-on-surface">Job Summary</h3>
              </div>
              <p className="text-body-sm text-on-surface-variant leading-relaxed">
                {scanResult.jobSummary}
              </p>
            </div>
          )}

          {(scanResult.companyName || (scanResult.secRegistration && scanResult.secRegistration.length > 0) || (scanResult.webSearch && (scanResult.webSearch.legitimacy?.length || scanResult.webSearch.scam_reports?.length))) && (
            <div className="flex flex-col gap-3 p-4 rounded-xl bg-surface-container-low border border-outline-variant/20">
              <div className="flex items-center gap-2">
                <Icon name="business" className="text-secondary" />
                <h3 className="text-label-md font-bold text-on-surface">Company Information</h3>
              </div>

              {scanResult.companyName && (
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="text-body-sm text-on-surface-variant">Company:</span>
                  <span className="text-body-sm font-bold text-on-surface break-words min-w-0">{scanResult.companyName}</span>
                </div>
              )}

              {scanResult.secRegistration && scanResult.secRegistration.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-label-sm font-bold text-on-surface-variant">SEC Registration</span>
                  {scanResult.secRegistration.map((sec, i) => (
                    <div key={i} className="flex flex-col gap-0.5 p-2 rounded-lg bg-surface-container-highest/50">
                      <span className="text-body-sm text-on-surface">{sec.company_name}</span>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-body-sm text-on-surface-variant">
                        {sec.sec_no && <span className="break-all">SEC# {sec.sec_no}</span>}
                        {sec.status && <span className={`font-bold ${sec.status.toLowerCase().includes('active') ? 'text-green-400' : 'text-amber-400'}`}>{sec.status}</span>}
                        {sec.date_approved && <span>{sec.date_approved}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {scanResult.webSearch?.legitimacy && scanResult.webSearch.legitimacy.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-label-sm font-bold text-on-surface-variant">Web Results</span>
                  {scanResult.webSearch.legitimacy.map((r, i) => (
                    <div key={i} className="flex flex-col gap-0.5">
                      <span className="text-body-sm text-on-surface line-clamp-1">{r.title}</span>
                      <span className="text-body-sm text-on-surface-variant line-clamp-2">{r.snippet}</span>
                    </div>
                  ))}
                </div>
              )}

              {scanResult.webSearch?.scam_reports && scanResult.webSearch.scam_reports.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-label-sm font-bold text-error">Scam Reports</span>
                  {scanResult.webSearch.scam_reports.map((r, i) => (
                    <div key={i} className="flex flex-col gap-0.5 p-2 rounded-lg bg-error-container/10 border border-error/20">
                      <span className="text-body-sm text-on-surface line-clamp-1">{r.title}</span>
                      <span className="text-body-sm text-on-surface-variant line-clamp-2">{r.snippet}</span>
                    </div>
                  ))}
                </div>
              )}

              {scanResult.webSearch?.linkedin && scanResult.webSearch.linkedin.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-label-sm font-bold text-on-surface-variant">LinkedIn</span>
                  {scanResult.webSearch.linkedin.map((r, i) => (
                    <div key={i} className="flex flex-col gap-0.5">
                      <span className="text-body-sm text-on-surface line-clamp-1">{r.title}</span>
                      <span className="text-body-sm text-on-surface-variant line-clamp-2">{r.snippet}</span>
                    </div>
                  ))}
                </div>
              )}

              {scanResult.webSearch?.dole && scanResult.webSearch.dole.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-label-sm font-bold text-on-surface-variant">DOLE Licensed Agency</span>
                  {scanResult.webSearch.dole.map((r, i) => (
                    <div key={i} className="flex flex-col gap-0.5">
                      <span className="text-body-sm text-on-surface line-clamp-1">{r.title}</span>
                      <span className="text-body-sm text-on-surface-variant line-clamp-2">{r.snippet}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {scanResult.emailVerifications && scanResult.emailVerifications.length > 0 && (
            <div className="flex flex-col gap-3 p-4 rounded-xl bg-surface-container-low border border-outline-variant/20">
              <div className="flex items-center gap-2">
                <Icon name="alternate_email" className="text-secondary" />
                <h3 className="text-label-md font-bold text-on-surface">Email Verification</h3>
              </div>
              {scanResult.emailVerifications.map((ev, i) => (
                <div key={i} className={`flex flex-col gap-1 p-2.5 rounded-lg border ${
                  ev.risk === 'high' ? 'bg-error-container/10 border-error/20' :
                  ev.risk === 'medium' ? 'bg-secondary-container/10 border-secondary/20' :
                  'bg-surface-container-highest/50 border-outline-variant/10'
                }`}>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="text-body-sm font-bold text-on-surface font-mono break-all">{ev.email}</span>
                    <span className={`text-body-sm font-bold px-1.5 py-0.5 rounded ${
                      ev.risk === 'high' ? 'bg-error/20 text-error' :
                      ev.risk === 'medium' ? 'bg-secondary/20 text-secondary' :
                      'bg-green-500/20 text-green-400'
                    }`}>
                      {ev.risk === 'high' ? 'HIGH RISK' : ev.risk === 'medium' ? 'MEDIUM' : 'VALID'}
                    </span>
                  </div>
                  <span className="text-body-sm text-on-surface-variant break-words">{ev.reason}</span>
                </div>
              ))}
            </div>
          )}

          {scanResult.externalVerification && (() => {
            const ev = scanResult.externalVerification;
            const hasAny = (ev.phones?.length || 0) + (ev.domains?.length || 0) + (ev.websites?.length || 0) + (ev.social?.length || 0) + (ev.gov?.length || 0) + (ev.scam_lists?.length || 0) > 0;
            if (!hasAny) return null;
            return (
              <div className="flex flex-col gap-3 p-4 rounded-xl bg-surface-container-low border border-outline-variant/20">
                <div className="flex items-center gap-2">
                  <Icon name="search" className="text-secondary" />
                  <h3 className="text-label-md font-bold text-on-surface">External Verification</h3>
                </div>

                {ev.phones && ev.phones.length > 0 && ev.phones.map((p, i) => (
                  <div key={`ph-${i}`} className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-body-sm p-2 rounded-lg ${p.risk === 'high' ? 'bg-error-container/10' : p.risk === 'medium' ? 'bg-secondary-container/10' : 'bg-surface-container-highest/50'}`}>
                    <Icon name="phone_disabled" className={p.risk === 'high' ? 'text-error' : 'text-on-surface-variant'} />
                    <span className="font-mono text-on-surface break-all">{p.number}</span>
                    <span className={`font-bold ${p.risk === 'high' ? 'text-error' : p.risk === 'medium' ? 'text-secondary' : 'text-green-400'}`}>
                      {p.risk === 'high' ? 'INVALID' : p.carrier || 'VALID'}
                    </span>
                    <span className="text-on-surface-variant min-w-0 break-words">{p.reason}</span>
                  </div>
                ))}

                {ev.domains && ev.domains.length > 0 && ev.domains.map((d, i) => (
                  <div key={`dom-${i}`} className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-body-sm p-2 rounded-lg ${d.risk === 'high' ? 'bg-error-container/10' : d.risk === 'medium' ? 'bg-secondary-container/10' : 'bg-surface-container-highest/50'}`}>
                    <Icon name="info" className={d.risk === 'high' ? 'text-error' : 'text-on-surface-variant'} />
                    <span className="font-mono text-on-surface break-all">{d.domain}</span>
                    <span className={`font-bold ${d.risk === 'high' ? 'text-error' : d.risk === 'medium' ? 'text-secondary' : 'text-green-400'}`}>
                      {d.age_months != null ? `${d.age_months}mo old` : 'UNKNOWN'}
                    </span>
                    <span className="text-on-surface-variant min-w-0 break-words">{d.reason}</span>
                  </div>
                ))}

                {ev.websites && ev.websites.length > 0 && ev.websites.map((w, i) => (
                  <div key={`web-${i}`} className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-body-sm p-2 rounded-lg ${w.risk === 'high' ? 'bg-error-container/10' : w.risk === 'medium' ? 'bg-secondary-container/10' : 'bg-surface-container-highest/50'}`}>
                    <Icon name="open_in_new" className={w.alive ? 'text-green-400' : 'text-error'} />
                    <span className="font-mono text-on-surface truncate min-w-0 max-w-full">{w.url}</span>
                    <span className={`font-bold ${w.alive ? 'text-green-400' : 'text-error'}`}>
                      {w.alive ? `HTTP ${w.status_code}` : 'DEAD'}
                    </span>
                  </div>
                ))}

                {ev.social && ev.social.length > 0 && ev.social.map((s, i) => (
                  <div key={`soc-${i}`} className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-body-sm p-2 rounded-lg ${s.found ? 'bg-surface-container-highest/50' : 'bg-secondary-container/10'}`}>
                    <Icon name={s.platform === 'facebook' ? 'smart_toy' : 'work'} className={s.found ? 'text-green-400' : 'text-secondary'} />
                    <span className="text-on-surface capitalize">{s.platform}</span>
                    <span className={`font-bold ${s.found ? 'text-green-400' : 'text-secondary'}`}>
                      {s.found ? 'FOUND' : 'NOT FOUND'}
                    </span>
                    {s.title && <span className="text-on-surface-variant truncate min-w-0 max-w-full">{s.title}</span>}
                  </div>
                ))}

                {ev.gov && ev.gov.length > 0 && ev.gov.map((g, i) => (
                  <div key={`gov-${i}`} className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-body-sm p-2 rounded-lg ${g.found ? 'bg-surface-container-highest/50' : 'bg-secondary-container/10'}`}>
                    <Icon name="badge" className={g.found ? 'text-green-400' : 'text-secondary'} />
                    <span className="text-on-surface">{g.registry}</span>
                    <span className={`font-bold ${g.found ? 'text-green-400' : 'text-secondary'}`}>
                      {g.found ? 'REGISTERED' : 'NOT FOUND'}
                    </span>
                    {g.details && <span className="text-on-surface-variant min-w-0 max-w-full break-words">{g.details}</span>}
                  </div>
                ))}

                {ev.scam_lists && ev.scam_lists.length > 0 && ev.scam_lists.map((s, i) => (
                  s.found && (
                    <div key={`scam-${i}`} className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-body-sm p-2 rounded-lg ${s.risk === 'high' ? 'bg-error-container/10' : 'bg-secondary-container/10'}`}>
                      <Icon name="warning" className="text-error" />
                      <span className="text-on-surface">Scam Reports: {s.count}</span>
                      <span className={`font-bold ${s.risk === 'high' ? 'text-error' : 'text-secondary'}`}>
                        {s.risk === 'high' ? 'MULTIPLE REPORTS' : '1 REPORT'}
                      </span>
                    </div>
                  )
                ))}
              </div>
            );
          })()}
        </>
      )}

      {isLoading && !hasScanned && !scanResult && (
        <section className="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-5 mb-stack-md tactile-card">
          <div className="flex flex-col items-center gap-4 text-center">
            <div className="relative w-[132px] h-[132px] flex items-center justify-center shrink-0">
              <div className="w-[132px] h-[132px] rounded-full bg-surface-container-high animate-pulse" />
            </div>
            <div className="flex flex-col gap-1.5 min-w-0 w-full">
              <div className="mx-auto w-32 h-4 rounded bg-surface-container-high animate-pulse" />
              <div className="mx-auto w-full max-w-[220px] h-3 rounded bg-surface-container-high animate-pulse" />
              <div className="mx-auto w-3/4 max-w-[180px] h-3 rounded bg-surface-container-high animate-pulse" />
            </div>
            <div className="flex items-center gap-2 text-on-surface-variant">
              <span className="w-2 h-2 rounded-full bg-secondary animate-ping" />
              <span className="font-label-md">Scanning… {progressPercent}%</span>
            </div>
          </div>
        </section>
      )}

      {hasScanned && !isValidJob && scanResult && (
        <InvalidContentError onRetry={resetAll} />
      )}

      <ScanActions
        onPickElement={handlePickElement}
        onCancelPick={() => setPickerCancelPhase((p) => p + 1)}
        isPickerActive={pickerActive}
        isPickerActivating={pickerActivating}
        onManualCrop={() => setCropPhase((p) => p + 1)}
        onCancelCrop={() => setCropCancelPhase((p) => p + 1)}
        isCropActive={cropActive}
        isCropActivating={cropActivating}
        afterScan={hasScanned}
        disabled={isLoading}
      />

      {screenshots.length > 0 && !hasScanned && (
        <div className="flex flex-col gap-3">
          <div className={`grid gap-2 ${screenshots.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
            {screenshots.map((ss, i) => (
              <div key={i} className={`relative rounded-lg overflow-hidden border border-outline-variant/20 bg-surface-container cursor-pointer group ${
                screenshots.length === 1 ? 'max-h-80' : 'aspect-square'
              }`} onClick={() => setLightboxIndex(i)}>
                <img src={ss} alt={`Selected ${i + 1}`} className={`w-full h-full ${screenshots.length === 1 ? 'object-contain' : 'object-cover'}`} />
                <button
                  onClick={(e) => { e.stopPropagation(); removeScreenshot(i); }}
                  className="absolute top-2 right-2 w-7 h-7 flex items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors"
                >
                  <Icon name="close" className="text-sm" />
                </button>
              </div>
            ))}
          </div>
          <button
            onClick={handleScan}
            disabled={isLoading}
            className="w-full tactile-btn-gold py-3 rounded-lg font-headline-md text-base flex items-center justify-center gap-2 disabled:opacity-70 active:translate-y-[1px]"
          >
            <Icon name="security" />
            {isLoading ? 'Scanning...' : `Scan (${screenshots.length})`}
          </button>
        </div>
      )}

      {lightboxIndex !== null && (
        <div
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center"
          onClick={() => setLightboxIndex(null)}
        >
          <button
            onClick={() => setLightboxIndex(null)}
            className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors z-10"
          >
            <Icon name="close" className="text-lg" />
          </button>

          {screenshots.length > 1 && lightboxIndex > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); setLightboxIndex(lightboxIndex - 1); }}
              className="absolute left-4 top-1/2 -translate-y-1/2 w-10 h-10 flex items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors z-10"
            >
              <Icon name="chevron_left" className="text-2xl" />
            </button>
          )}

          {screenshots.length > 1 && lightboxIndex < screenshots.length - 1 && (
            <button
              onClick={(e) => { e.stopPropagation(); setLightboxIndex(lightboxIndex + 1); }}
              className="absolute right-4 top-1/2 -translate-y-1/2 w-10 h-10 flex items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors z-10"
            >
              <Icon name="chevron_right" className="text-2xl" />
            </button>
          )}

          <img
            src={screenshots[lightboxIndex]}
            alt={`Full size screenshot ${lightboxIndex + 1}`}
            className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />

          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-black/60 text-white text-label-sm">
            {lightboxIndex + 1} / {screenshots.length}
          </div>
        </div>
      )}

      <PickerButton
        forceActivate={pickerPhase}
        forceCancel={pickerCancelPhase}
        forceManualCrop={cropPhase}
        forceCropCancel={cropCancelPhase}
        onActiveChange={setPickerActive}
        onActivatingChange={setPickerActivating}
        onCropActiveChange={setCropActive}
        onCropActivatingChange={setCropActivating}
        onSelectionChange={handleSelectionChange}
        onScreenshotReady={handleScreenshotReady}
      />
    </div>
  );
}

export default ScamScanView;
