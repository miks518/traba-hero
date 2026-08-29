import React from 'react';
import TrabaheroLogo from '../sidepanel/components/common/TrabaheroLogo';

const iconMap: Record<string, string> = {
  scan: 'security',
  match: 'description',
  launch: 'open_in_new',
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
          <TrabaheroLogo size={20} className="text-gold-gradient" />
          <span className="text-headline-sm font-headline font-bold text-gold-gradient">
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
          className="tactile-btn-gold flex items-center justify-center gap-2 w-full py-3 px-4 rounded-lg text-body-md uppercase tracking-[0.02em] cursor-pointer select-none"
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
      </main>

      <footer className="bg-surface-container-lowest border-t border-outline-variant/10 w-full flex items-center justify-center p-3 shrink-0">
        <span className="text-label-sm text-on-surface-variant opacity-60">
          © 2026 Trabahero
        </span>
      </footer>
    </div>
  );
}