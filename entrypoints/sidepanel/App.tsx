import React, { useState, useCallback, useEffect, useRef } from 'react';
import { TopAppBar, SideNav, Footer, OfflineBanner } from './components/shell';
import { ScamScanView } from './views/ScamScanView';
import { ResumeMatchView } from './views/ResumeMatchView';
// TEMPORARY debug view for the web search. Remove with the 'search' nav tab.
import { SearchDebugView } from './views/SearchDebugView';
import { useBackendHealth } from './hooks/useBackendHealth';
import { migrateScannedJobs } from './lib/scanHistory';
import type { ScanProgress } from './lib/api';
import type { ViewId, ScannedJob, ResumeData } from './types';
import type { TextSize } from './components/shell/TopAppBar';

function getInitialTheme(): 'dark' | 'light' {
  return 'dark';
}

export default function App() {
  const [activeView, setActiveView] = useState<ViewId>('scan');
  const [scannedJobs, setScannedJobs] = useState<ScannedJob[]>([]);
  const [resumeData, setResumeData] = useState<ResumeData | null>(null);
  const [scanProgress, setScanProgress] = useState<ScanProgress | null>(null);
  const [resumeMatchProgress, setResumeMatchProgress] = useState<ScanProgress | null>(null);
  const [theme, setTheme] = useState<'dark' | 'light'>(getInitialTheme);
  const [textSize, setTextSize] = useState<TextSize>('default');
  const { isOnline, isChecking, checkNow } = useBackendHealth();

  const handleTabChange = useCallback((id: ViewId) => {
    if (id === activeView) return;
    setActiveView(id);
  }, [activeView]);

  useEffect(() => {
    try {
      // @ts-ignore - storage API available in extension context
      chrome.storage.local.get(['theme', 'textSize', 'scannedJobs'], (result) => {
        const storedTheme = result.theme as string | undefined;
        if (storedTheme === 'light' || storedTheme === 'dark') {
          setTheme(storedTheme);
          document.documentElement.classList.toggle('dark', storedTheme === 'dark');
        }
        const storedSize = result.textSize as string | undefined;
        if (storedSize === 'default' || storedSize === 'big' || storedSize === 'largest') {
          setTextSize(storedSize);
        }
        const storedJobs = migrateScannedJobs(result.scannedJobs);
        if (storedJobs.length > 0) {
          setScannedJobs(storedJobs);
        }
      });
    } catch {}
  }, []);

  const handleToggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      document.documentElement.classList.toggle('dark', next === 'dark');
      try {
        // @ts-ignore - storage API available in extension context
        chrome.storage.local.set({ theme: next });
      } catch {}
      return next;
    });
  }, []);

  const handleTextSizeChange = useCallback((size: TextSize) => {
    setTextSize(size);
    try {
      // @ts-ignore - storage API available in extension context
      chrome.storage.local.set({ textSize: size });
    } catch {}
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  const handleScanComplete = useCallback((job: ScannedJob) => {
    setScannedJobs((prev) => [...prev, job]);
  }, []);

  // Persist scanned jobs to storage
  useEffect(() => {
    try {
      // @ts-ignore - storage API available in extension context
      chrome.storage.local.set({ scannedJobs });
    } catch {}
  }, [scannedJobs]);

  const handleResumeData = useCallback((data: ResumeData) => {
    setResumeData(data);
  }, []);

  const handleClearJobs = useCallback(() => {
    setScannedJobs([]);
    try {
      // @ts-ignore - storage API available in extension context
      chrome.storage.local.set({ scannedJobs: [] });
    } catch {}
  }, []);

  const handleClearResume = useCallback(() => {
    setResumeData(null);
  }, []);

  return (
    <div className={`w-full h-screen bg-background text-on-surface flex flex-col overflow-hidden font-body text-body-md ${textSize === 'big' ? 'text-size-big' : textSize === 'largest' ? 'text-size-largest' : 'text-size-default'}`}>
      <TopAppBar onClose={() => window.close()} theme={theme} onToggleTheme={handleToggleTheme} textSize={textSize} onTextSizeChange={handleTextSizeChange} />
      <OfflineBanner isOnline={isOnline} isChecking={isChecking} onRetry={checkNow} />
      <div className="flex flex-1 overflow-hidden">
        <SideNav
          activeView={activeView}
          onTabClick={handleTabChange}
          scannedJobsCount={scannedJobs.length}
          scanningProgress={resumeMatchProgress || scanProgress}
          isLocked={false}
        />
        <main className="flex-1 flex flex-col overflow-y-auto custom-scroll bg-background">
          <div
            className={`h-full flex-col ${activeView === 'scan' ? 'flex' : 'hidden'}`}
          >
            <ScamScanView onScanComplete={handleScanComplete} onScanProgressChange={setScanProgress} isOnline={isOnline} />
          </div>
          <div
            className={`h-full flex-col ${activeView === 'match' ? 'flex' : 'hidden'}`}
          >
            <ResumeMatchView
              scannedJobs={scannedJobs}
              resumeData={resumeData}
              onResumeData={handleResumeData}
              onClearResume={handleClearResume}
              onClearJobs={handleClearJobs}
              onProgressChange={setResumeMatchProgress}
              isOnline={isOnline}
            />
          </div>
          {/* TEMPORARY debug tab. Remove with SearchDebugView and the 'search' entry in NAV_TABS. */}
          <div
            className={`h-full flex-col ${activeView === 'search' ? 'flex' : 'hidden'}`}
          >
            <SearchDebugView />
          </div>
        </main>
      </div>
      <Footer />
    </div>
  );
}
