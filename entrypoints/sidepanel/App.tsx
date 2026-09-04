import React, { useState, useCallback, useEffect } from 'react';
import { TopAppBar, SideNav, Footer } from './components/shell';
import { ScamScanView } from './views/ScamScanView';
import { ResumeMatchView } from './views/ResumeMatchView';
import { ModelTestView } from './views/ModelTestView';
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
  const [scannedJobsCount, setScannedJobsCount] = useState(0);
  const [scanProgress, setScanProgress] = useState<ScanProgress | null>(null);
  const [theme, setTheme] = useState<'dark' | 'light'>(getInitialTheme);
  const [textSize, setTextSize] = useState<TextSize>('default');

  useEffect(() => {
    try {
      // @ts-ignore - storage API available in extension context
      chrome.storage.local.get(['theme', 'textSize'], (result) => {
        const storedTheme = result.theme as string | undefined;
        if (storedTheme === 'light' || storedTheme === 'dark') {
          setTheme(storedTheme);
          document.documentElement.classList.toggle('dark', storedTheme === 'dark');
        }
        const storedSize = result.textSize as string | undefined;
        if (storedSize === 'default' || storedSize === 'big' || storedSize === 'largest') {
          setTextSize(storedSize);
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
    setScannedJobsCount(scannedJobs.length + 1);
  }, [scannedJobs.length]);

  const handleResumeData = useCallback((data: ResumeData) => {
    setResumeData(data);
  }, []);

  const handleClearJobs = useCallback(() => {
    setScannedJobs([]);
    setScannedJobsCount(0);
  }, []);

  const handleClearResume = useCallback(() => {
    setResumeData(null);
  }, []);

  const hasHighRisk = scannedJobs.some((j) => j.scanResult.status === 'scam');
  const hasMediumRisk = scannedJobs.some((j) => j.scanResult.status === 'suspicious');

  return (
    <div className={`w-full h-screen bg-background text-on-surface flex flex-col overflow-hidden font-body text-body-md ${textSize === 'big' ? 'text-size-big' : textSize === 'largest' ? 'text-size-largest' : ''}`}>
      <TopAppBar onClose={() => window.close()} theme={theme} onToggleTheme={handleToggleTheme} textSize={textSize} onTextSizeChange={handleTextSizeChange} />
      <div className="flex flex-1 overflow-hidden">
        <SideNav
          activeView={activeView}
          onTabClick={setActiveView}
          scannedJobsCount={scannedJobsCount}
          scanningProgress={scanProgress}
          isLocked={hasHighRisk}
        />
        <main className="flex-1 flex flex-col overflow-y-auto custom-scroll bg-background">
          <div className={`h-full flex-col ${activeView === 'scan' ? 'flex' : 'hidden'}`}>
            <ScamScanView onScanComplete={handleScanComplete} onScanProgressChange={setScanProgress} />
          </div>
          <div className={`h-full flex-col ${activeView === 'match' ? 'flex' : 'hidden'}`}>
            <ResumeMatchView
              scannedJobs={scannedJobs}
              resumeData={resumeData}
              onResumeData={handleResumeData}
              onClearResume={handleClearResume}
              onClearJobs={handleClearJobs}
              isLocked={hasHighRisk}
              hasWarnings={hasMediumRisk}
            />
          </div>
          <div className={`h-full flex-col ${activeView === 'test' ? 'flex' : 'hidden'}`}>
            <ModelTestView />
          </div>
        </main>
      </div>
      <Footer />
    </div>
  );
}
