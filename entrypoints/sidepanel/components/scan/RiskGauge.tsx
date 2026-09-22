import React from 'react';
import { FormattedText } from '../common/FormattedText';
import type { ScanRiskLevel } from '../../types';

export interface RiskGaugeProps {
  score: number;
  description: string;
  maxScore?: number;
  riskLevel?: ScanRiskLevel;
  riskLabel?: string;
  status?: 'scam' | 'suspicious' | 'legitimate';
}

function scoreColor(score: number): string {
  const hue = Math.max(0, 120 - (score / 100) * 120);
  return `hsl(${hue}, 78%, 44%)`;
}

function levelColor(level: ScanRiskLevel): string {
  switch (level) {
    case 'critical': return 'hsl(0, 78%, 44%)';
    case 'high': return 'hsl(25, 78%, 44%)';
    case 'moderate': return 'hsl(45, 78%, 44%)';
    case 'low': return scoreColor(15);
  }
}

export function RiskGauge({ score, description, maxScore = 100, riskLevel = 'low', riskLabel = 'Low Risk', status }: RiskGaugeProps) {
  const normalized = Math.min(score / maxScore, 1);
  const pct = Math.round(normalized * 100);
  const color = levelColor(riskLevel);

  const radius = 52;
  const strokeWidth = 14;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - normalized);

  return (
    <section className="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-5 mb-stack-md tactile-card">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="relative w-[132px] h-[132px] flex items-center justify-center shrink-0">
          <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 128 128">
            <circle
              cx="64" cy="64"
              fill="transparent"
              r={radius}
              stroke="currentColor"
              strokeWidth={strokeWidth}
              className="text-surface-container-high"
            />
            <circle
              cx="64" cy="64"
              fill="transparent"
              r={radius}
              stroke={color}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              className="transition-all duration-1000 ease-out drop-shadow-[0_0_6px_var(--tw-shadow-color)]"
              style={{ filter: `drop-shadow(0 0 6px ${color}40)` }}
            />
          </svg>
          <div className="flex flex-col items-center">
            <span className="text-3xl font-extrabold tracking-tight leading-none" style={{ color }}>{pct}</span>
            <span className="font-label-md text-label-md text-on-surface-variant mt-0.5">RISK</span>
          </div>
        </div>
        <div className="flex flex-col gap-1.5 min-w-0">
          <span
            className="font-headline-xs font-bold inline-flex items-center justify-center gap-1.5"
            style={{ color }}
          >
            <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
            {riskLabel}
          </span>
          <FormattedText text={description} className="font-body-md" />
        </div>
      </div>
    </section>
  );
}

export default RiskGauge;
