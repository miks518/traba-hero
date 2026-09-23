import React, { useState, useCallback, useEffect, useRef } from 'react';
import { RiskGauge, RedFlagsList, ScanActions, PickerButton, InvalidContentError, VerificationSection } from '../components/scan';
import { Icon, ToastContainer, useToastManager } from '../components/common';
import { scanScreenshotStream, verifyJobStream, ApiRequestError, type ScanProgress } from '../lib/api';
import { compressImage } from '../lib/imageUtils';
import type { ScanResult, IconName, ScannedJob, ApiScanResponse, ScanRiskLevel } from '../types';

function getRiskLevel(score: number): ScanRiskLevel {
  if (score >= 76) return 'critical';
  if (score >= 46) return 'high';
  if (score >= 16) return 'moderate';
  return 'low';
}

function getRiskLabel(score: number): string {
  if (score >= 76) return 'Critical Risk';
  if (score >= 46) return 'High Risk';
  if (score >= 16) return 'Moderate Risk';
  return 'Low Risk';
}

function riskLevelLabel(level: string): string {
  switch (level) {
    case 'low': return 'Low Risk';
    case 'moderate': return 'Moderate Risk';
    case 'high': return 'High Risk';
    case 'critical': return 'Critical Risk';
    default: return 'Low Risk';
  }
}

export interface ScamScanViewProps {
  onScanComplete?: (job: ScannedJob) => void;
  onScanProgressChange?: (progress: ScanProgress | null) => void;
}

const SEVERITY_ICONS: Record<string, IconName> = {
  low: 'info',
  mid: 'warning',
  high: 'warning',
};

function generateJobId(): string {
  return `job-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function mapApiResponse(data: ApiScanResponse): ScanResult {
  const isJobPosting = data.valid;
  const flags = data.red_flags ?? [];
  const hasCritical = flags.some((f) => f.severity === 'high');
  const flagCount = flags.length;

  let status: ScanResult['status'];
  if (!isJobPosting) {
    status = 'legitimate';
  } else if (hasCritical || flagCount >= 2) {
    status = 'scam';
  } else if (flagCount === 1) {
    status = 'suspicious';
  } else {
    status = 'legitimate';
  }
  const riskLevel = status === 'scam' ? 'critical' : status === 'suspicious' ? 'high' : 'low';
  const riskScore = riskLevel === 'critical' ? 80 : riskLevel === 'high' ? 50 : 10;
  return {
    status,
    riskLevel,
    riskLabel: riskLevelLabel(riskLevel),
    statusTitle: riskLevelLabel(riskLevel),
    scanningTarget: 'Scanned Element',
    riskScore,
    riskDescription: data.job_summary || 'Scan completed.',
    redFlags: flags.map((f, i) => ({
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
    verificationResult: data.verificationResult,
    verificationLoading: data.verification_context ? true : data.verificationLoading,
    verificationError: data.verificationError,
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
  const verifyAbortRef = useRef<AbortController | null>(null);
  const [currentSearchQuery, setCurrentSearchQuery] = useState('');
  const [verificationFailed, setVerificationFailed] = useState(false);

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
    return () => {
      abortRef.current?.abort();
      verifyAbortRef.current?.abort();
    };
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
    setVerificationFailed(false);
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
      setVerificationFailed(false);
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
      console.log('[scan] data.valid=%s, data.verification_context=%s', data.valid, JSON.stringify(data.verification_context));
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
          id: generateJobId(),
          title: jobTitle,
          summary: data.job_summary,
          timestamp: new Date().toISOString(),
          scanResult: mapped,
        });

        // Trigger async verification if company name is available
        const verifyCtx = data.verification_context;
        console.log('[scan] verifyCtx=', JSON.stringify(verifyCtx));
        if (verifyCtx?.company_name) {
          startVerification({
            company_name: verifyCtx.company_name,
            job_summary: verifyCtx.job_summary || data.job_summary || '',
            red_flags: data.red_flags,
          });
        }
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

  const startVerification = useCallback(async (context: {
    company_name: string;
    job_summary: string;
    red_flags?: { flag: string; reasoning: string; severity: string }[];
  }) => {
    console.log('[verify] Starting verification for:', context.company_name);
    verifyAbortRef.current?.abort();
    const controller = new AbortController();
    verifyAbortRef.current = controller;

    setScanResult(prev => prev ? { ...prev, verificationLoading: true, verificationError: false } : null);
    setCurrentSearchQuery('');
    setVerificationFailed(false);

    try {
      const verifyResult = await verifyJobStream(
        context,
        controller.signal,
        (p) => setProgress(p),
        (query) => setCurrentSearchQuery(query),
      );

      console.log('[verify] verifyResult:', verifyResult);

      if (verifyResult.result) {
        console.log('[verify] Result received:', verifyResult.result);
        const result = verifyResult.result;
        setScanResult(prev => prev ? {
          ...prev,
          verificationResult: result,
          verificationLoading: false,
          verificationFailed: false,
          riskScore: result.riskScore ?? prev.riskScore,
          riskLevel: (result.riskLevel as ScanResult['riskLevel']) ?? prev.riskLevel,
          riskLabel: riskLevelLabel((result.riskLevel as ScanResult['riskLevel']) ?? prev.riskLevel),
          statusTitle: riskLevelLabel((result.riskLevel as ScanResult['riskLevel']) ?? prev.riskLevel),
        } : null);
      } else {
        console.warn('[verify] Empty result from verifyJobStream');
        setVerificationFailed(true);
        setScanResult(prev => prev ? { ...prev, verificationLoading: true } : null);
      }
    } catch (e) {
      console.error('[verify] Error:', e);
      setVerificationFailed(true);
      setScanResult(prev => prev ? { ...prev, verificationLoading: true, verificationError: true } : null);
    }
  }, []);

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
    return 'Something went wrong during the scan. Please try again later.';
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
          {scanResult.verificationLoading || verificationFailed ? (
            <section className="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-5 mb-stack-md tactile-card">
              <div className="flex flex-col items-center gap-4 text-center">
                <div className="relative w-[132px] h-[132px] flex items-center justify-center shrink-0">
                  <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 128 128">
                    <circle cx="64" cy="64" fill="transparent" r={52} stroke="currentColor" strokeWidth={14} className="text-surface-container-high" />
                    <circle cx="64" cy="64" fill="transparent" r={52} stroke="currentColor" strokeWidth={14} strokeLinecap="round" strokeDasharray={327} strokeDashoffset={327} className="animate-spin" style={{ color: 'hsl(45, 78%, 44%)' }} />
                  </svg>
                  <div className="flex flex-col items-center">
                    <span className="text-3xl font-extrabold tracking-tight leading-none animate-pulse">—</span>
                    <span className="font-label-md text-label-md text-on-surface-variant mt-0.5">RISK</span>
                  </div>
                </div>
                <div className="flex flex-col gap-1.5 min-w-0">
                  <span className="font-headline-xs font-bold inline-flex items-center justify-center gap-1.5 text-on-surface-variant">
                    <span className="w-2 h-2 rounded-full shrink-0 bg-secondary animate-ping" />
                    {verificationFailed ? 'Verification Unavailable' : 'Verifying...'}
                  </span>
                  <span className="text-body-sm text-on-surface-variant">
                    {verificationFailed ? 'Could not verify this company. Retry may be needed.' : 'Please wait while we verify this company.'}
                  </span>
                </div>
              </div>
            </section>
          ) : (
            <RiskGauge score={scanResult.riskScore} description={scanResult.riskDescription} riskLevel={scanResult.riskLevel} riskLabel={scanResult.riskLabel} />
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

          <VerificationSection
            result={scanResult.verificationResult}
            loading={scanResult.verificationLoading}
            error={scanResult.verificationError}
            currentQuery={currentSearchQuery}
            noCompanyName={isValidJob && !scanResult.verificationResult && !scanResult.verificationLoading && !scanResult.verificationError}
          />
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
              <div key={i} className={`relative rounded-lg overflow-hidden border border-outline-variant/20 bg-surface-container cursor-pointer group ${screenshots.length === 1 ? 'max-h-80' : 'aspect-square'
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
