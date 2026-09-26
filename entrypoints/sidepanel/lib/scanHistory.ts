import type { ScannedJob } from '../types';

/**
 * Repairs scan history written before external verification became the only
 * source of a risk score.
 *
 * Those entries carry a synthesised `riskScore` of 80/50/10 that was derived
 * from the number of red flags, not from any measured value. Showing it as a
 * percentage would present an invented number as a finding, so it is cleared on
 * load and the job is presented as unverified until it is scanned again.
 */
export function migrateScannedJobs(stored: unknown): ScannedJob[] {
  if (!Array.isArray(stored)) return [];

  return (stored as ScannedJob[]).map((job) => {
    const scanResult = job?.scanResult;
    if (!scanResult || typeof scanResult !== 'object') return job;
    if (scanResult.riskScored === true) return job;

    return {
      ...job,
      scanResult: {
        ...scanResult,
        riskScored: false,
        riskScore: null,
        riskLevel: null,
        riskLabel: 'Not Scored',
      },
    };
  });
}
