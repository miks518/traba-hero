import React, { useState, useCallback, useEffect } from 'react';
import { TopAppBar, SideNav, Footer } from './components/shell';
import { ScamScanView } from './views/ScamScanView';
import { ResumeMatchView } from './views/ResumeMatchView';
import { ModelTestView } from './views/ModelTestView';
import type { ScanProgress } from './lib/api';
import type { ViewId, ScannedJob, ResumeData } from './types';

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

  const handleToggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      document.documentElement.classList.toggle('dark', next === 'dark');
      return next;
    });
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

  return (
    <div className="w-full h-screen bg-background text-on-surface flex flex-col overflow-hidden font-body text-body-md">
      <TopAppBar onClose={() => window.close()} theme={theme} onToggleTheme={handleToggleTheme} />
      <div className="flex flex-1 overflow-hidden">
        <SideNav
          activeView={activeView}
          onTabClick={setActiveView}
          scannedJobsCount={scannedJobsCount}
          scanningProgress={scanProgress}
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
