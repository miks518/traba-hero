import React, { useState, useEffect } from 'react';
import TrabaheroLogo from '../sidepanel/components/common/TrabaheroLogo';

const iconMap: Record<string, string> = {
  scan: 'security',
  match: 'description',
  launch: 'open_in_new',
  fab: 'shield_person',
};

function PopupIcon({
  name,
  className = '',
  ...rest
}: {
  name: string;
  className?: string;
} & React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={`material-symbols-outlined ${className}`} {...rest}>
      {iconMap[name] ?? name}
    </span>
  );
}

export default function App() {
  const [fabEnabled, setFabEnabled] = useState(true);

  useEffect(() => {
    try {
      // @ts-ignore - storage API available in extension context
      chrome.storage.local.get('fabEnabled', (result) => {
        if (result.fabEnabled === false) setFabEnabled(false);
      });
    } catch {}
  }, []);

  const handleToggleFab = () => {
    const next = !fabEnabled;
    setFabEnabled(next);
    try {
      // @ts-ignore - storage API available in extension context
      chrome.storage.local.set({ fabEnabled: next });
    } catch {}
  };

  const openSidepanel = () => {
    browser.tabs.query({ active: true, currentWindow: true }).then((tabs) => {
      if (tabs[0]?.id) {
        // @ts-ignore - sidePanel API is available in Chrome MV3
        chrome.sidePanel.open({ tabId: tabs[0].id });
      }
    });
    window.close();
  };

  return (
    <div className="w-[320px] bg-background text-on-surface font-body text-body-md flex flex-col">
      <header className="bg-surface-container border-b border-outline-variant/30 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)] flex justify-between items-center px-4 py-3 shrink-0">
        <div className="flex items-center gap-2">
          <TrabaheroLogo size={20} className="text-accent-gradient" />
          <span className="text-headline-sm font-headline font-bold text-accent-gradient">
            Trabahero
          </span>
        </div>
        <PopupIcon
          name="launch"
          className="cursor-pointer text-on-surface-variant hover:text-secondary transition-colors active:scale-95"
          onClick={openSidepanel}
          title="Open full panel"
        />
      </header>

      <main className="flex flex-col gap-4 p-4">
        <p className="text-body-sm text-on-surface-variant text-center">
          AI-powered job scam detection & resume matching for Filipino job seekers
        </p>

        <button
          onClick={openSidepanel}
          className="tactile-btn-accent flex items-center justify-center gap-2 w-full py-3 px-4 rounded-lg text-body-md uppercase tracking-[0.02em] cursor-pointer select-none"
        >
          <PopupIcon name="scan" />
          Open Trabahero
        </button>

        <div className="grid grid-cols-2 gap-3">
          <div className="tactile-card bg-surface-container rounded-xl p-3">
            <div className="flex flex-col items-center gap-1">
              <PopupIcon name="scan" className="text-secondary text-[28px]" />
              <span className="text-label-md text-on-surface-variant uppercase tracking-[0.02em]">
                Scam Scan
              </span>
              <span className="text-body-sm text-on-surface-variant opacity-70 text-center">
                Detect fraudulent listings in real-time
              </span>
            </div>
          </div>

          <div className="tactile-card bg-surface-container rounded-xl p-3">
            <div className="flex flex-col items-center gap-1">
              <PopupIcon name="match" className="text-secondary text-[28px]" />
              <span className="text-label-md text-on-surface-variant uppercase tracking-[0.02em]">
                Resume Match
              </span>
              <span className="text-body-sm text-on-surface-variant opacity-70 text-center">
                Compare your resume to job requirements
              </span>
            </div>
          </div>
        </div>

        <div className="tactile-card bg-surface-container rounded-xl p-3 flex items-center gap-3">
          <PopupIcon name="fab" className="text-secondary text-[24px] shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="text-label-md text-on-surface block">
              Floating Button
            </span>
            <span className="text-body-sm text-on-surface-variant opacity-70">
              Show scan button on pages
            </span>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={fabEnabled}
            onClick={handleToggleFab}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out ${
              fabEnabled
                ? 'bg-secondary'
                : 'bg-surface-container-highest border border-outline-variant'
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 transform rounded-full shadow-card ring-0 transition duration-200 ease-in-out mt-px ${
                fabEnabled
                  ? 'translate-x-[22px] bg-on-secondary'
                  : 'translate-x-[1px] bg-outline'
              }`}
            />
          </button>
        </div>
      </main>

      <footer className="bg-surface-container-lowest border-t border-outline-variant/10 w-full flex items-center justify-center p-3 shrink-0">
        <span className="text-label-sm text-on-surface-variant opacity-60">
          © 2026 Trabahero
        </span>
      </footer>
    </div>
  );
}