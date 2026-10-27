/**
 * Tombstone — the retired report components stay retired.
 *
 * **What was deleted, and the tests that went with it.**
 *
 * `ScamScanView.elevate.test.tsx` (7 tests) covered a promotion scheme that no
 * longer exists: a pair of sibling groups — evidence and prose — inverted on a
 * high or critical score so the evidence rose above the posting analysis. The
 * tests pinned which group came first once the score settled, that both stayed
 * mounted so a collapse state survived a score change, that the verification
 * section took the risk accent, and that a level arriving without a score still
 * promoted.
 *
 * Parts of `ScamScanView.test.tsx` went with it: the score-line tests, the
 * capture-reminder tests, and the provenance-jump tests. All asserted against
 * markup the report panel replaced.
 *
 * **Why a file of prose is a test.** `AGENTS.md`: *"Deleted is not dormant.
 * Functions removed from a module leave a tombstone test; a leftover helper is a
 * trap for the next reader."* `RiskGauge` was 321 lines and drew a magnitude arc
 * from `riskScore`. Nothing imports it any more, so nothing stops someone
 * reaching for it when they next want a number on the panel — and it would
 * compile, because the `riskScore` field is still on the wire. These assertions
 * are what make the deletion stick.
 *
 * **What is still open, and deliberately untested in this pass.** The behaviour
 * those tests protected did not go with the markup:
 *
 *   1. On a settled high or critical level, does `data-group="context"` land below
 *      `data-group="findings"` — and on anything else, above it? Promotion is
 *      *restated* rather than kept: the new stack has the assessment and the
 *      instructions at the top, so there is nothing above them to promote, and
 *      what promotion now means is the neutral context dropping below the
 *      findings.
 *   2. While verification is running, does it stay un-promoted? The scan returns
 *      a level from the posting alone and verification can move it, so reordering
 *      on the intermediate value would pull the reader's evidence out from under
 *      them and put it back a second later. The rule is still tested in
 *      `riskDisplay.test.ts` against `shouldElevateEvidence`, which is where it is
 *      decided; what is missing is that the panel honours it.
 *   3. Are both groups still mounted across a level change, so a collapsed
 *      disclosure does not re-expand itself?
 *
 * Also untested, and load-bearing: `assessmentCopy.ts` and `WhatWeChecked`'s derived
 * heading are new code. The score-line tests that were deleted asserted that no
 * figure appears anywhere on the panel and that it never tells a reader their
 * employer was unchecked after a lookup that confirmed everything. Those are
 * honesty assertions about new code with no test behind them yet. Writing them
 * was deferred — the UI first, no new tests in this pass — so they are recorded
 * here rather than left as an invisible gap.
 */

import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const scan = (...parts: string[]) => join(root, 'entrypoints/sidepanel/components/scan', ...parts);
const report = (...parts: string[]) =>
  join(root, 'entrypoints/sidepanel/components/report', ...parts);

/** Modules the report panel replaced. None may come back. */
const RETIRED: Array<[string, string]> = [
  ['RiskGauge', 'drew the magnitude arc from `riskScore`; replaced by the assessment banner'],
  ['AnomaliesList', 'replaced by `AnomalyCards`, which owns its own section heading'],
  ['EvidenceSummary', 'split across `WhatWeChecked` and `FullDetails`, per architecture §7.1'],
  ['VerificationCard', 'folded into the Verified / Contradicted / Could-not-verify lines'],
  ['PostingAnalysis', 'removed from the panel; its observational rule and word ban survive in the prompt'],
  ['JobSummary', 'removed from the panel, kept on the wire because the Match tab consumes it'],
];

describe('the retired report components', () => {
  it.each(RETIRED)('%s.tsx is gone — %s', (name) => {
    expect(existsSync(scan(`${name}.tsx`))).toBe(false);
  });

  it('are not exported from the barrel that replaced them', () => {
    // An export of a file that no longer exists would not compile, so this is a
    // guard against a *reimplementation* landing there under the old name, which
    // is the subtler version of the same trap.
    const barrel = join(root, 'entrypoints/sidepanel/components/scan/index.ts');
    const source = readFileSync(barrel, 'utf-8');
    for (const [name] of RETIRED) {
      expect(source, name).not.toMatch(new RegExp(`from '\\./${name}'`));
    }
  });
});

describe('what replaced them', () => {
  it.each([
    'ReportPanel',
    'AssessmentBlock',
    'ActionBlock',
    'AnomalyCards',
    'WhatWeChecked',
    'FullDetails',
    'ReportFooter',
    'JobMeta',
  ])('%s.tsx exists', (name) => {
    expect(existsSync(report(`${name}.tsx`))).toBe(true);
  });

  it('and the lifecycle they read from is out of the view', () => {
    // The view was over a thousand lines with the state machine, the two abort
    // lifecycles and the render interleaved. `useScanSession` is what makes the
    // panel readable on its own, so its absence would mean the split was undone.
    expect(
      existsSync(join(root, 'entrypoints/sidepanel/hooks/useScanSession.ts')),
    ).toBe(true);
  });
});
