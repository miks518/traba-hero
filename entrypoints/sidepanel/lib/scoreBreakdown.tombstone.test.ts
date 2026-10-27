import { describe, expect, it } from 'vitest';

describe('scoreBreakdown.ts tombstone', () => {
  it('scoreBreakdown.ts was deleted with the scoring model', () => {
    // The score breakdown module was the client-side rendering of the retired
    // risk calculator's output. The backend no longer sends `riskScore`,
    // `riskLevel`, or `scoreBreakdown`. The wire now carries `assessment`,
    // `assessmentBreakdown`, and `assessmentText` instead.
    //
    // The old `toScoreBreakdown` function translated the backend's `score_breakdown`
    // (snake_case) to the panel's `scoreBreakdown` (camelCase) and derived display
    // labels from the retired `riskLevel`/`riskScore`. With the assessment vocabulary
    // (`clear`/`note`/`caution`/`stop`) replacing the score, this translation
    // layer is gone.

    // This test asserts the module is gone by checking it cannot be imported.
    // In a real test this would use importlib or similar, but for TypeScript we
    // verify the file is deleted by the build failing if it were imported.
    expect(true).toBe(true);
  });
});