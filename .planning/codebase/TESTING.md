# Testing

## Current State

**No testing infrastructure exists.** The codebase has zero test files (`*.test.*`, `*.spec.*`), zero test configuration files, and zero testing dependencies in `package.json`.

| Aspect | Status |
|--------|--------|
| Test runner | Not configured (no Vitest, Jest, Playwright, etc.) |
| Test files | None found anywhere in the project |
| Test scripts in `package.json` | None |
| Coverage tool | Not configured |
| E2E framework | Not configured |
| Component testing | Not configured |
| Mocking library | Not configured |

The only verification in `package.json` scripts is `"compile": "tsc --noEmit"` — TypeScript type-checking only.

## Test Framework

**None configured.** If tests are added, the recommended framework setup based on the existing stack:

- **Recommended runner:** Vitest (natively compatible with Vite/WXT's Vite-based build pipeline)
- **Recommended component testing:** `@testing-library/react` + `@testing-library/jest-dom` (standard for React 19)
- **Recommended E2E:** Playwright (supports Chrome extensions)
- **Minimum viable setup in `package.json`:**
  ```json
  {
    "devDependencies": {
      "vitest": "^3.x",
      "@testing-library/react": "^16.x",
      "@testing-library/jest-dom": "^6.x",
      "jsdom": "^25.x"
    },
    "scripts": {
      "test": "vitest run",
      "test:watch": "vitest",
      "test:coverage": "vitest run --coverage"
    }
  }
  ```
- **Minimal `vitest.config.ts`:**
  ```ts
  import { defineConfig } from 'vitest/config';
  import react from '@vitejs/plugin-react';

  export default defineConfig({
    plugins: [react()],
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './test/setup.ts',
    },
  });
  ```

## What Should Be Tested

### Critical Unit Tests (Highest Priority)

| Component | File | What to test |
|-----------|------|--------------|
| **Icon** | `entrypoints/sidepanel/components/common/Icon.tsx` | Renders correct Material Symbols class and icon name; `fill`/`filled` prop sets `fontVariationSettings` correctly; spreads `className` and `style` correctly |
| **RiskGauge** | `entrypoints/sidepanel/components/scan/RiskGauge.tsx` | Renders score number and description; SVG progress circle has correct `strokeDashoffset` for 0%, 50%, 100%; `maxScore` prop clamps correctly |
| **SecurityBanner** | `entrypoints/sidepanel/components/scan/SecurityBanner.tsx` | Renders `statusTitle` and `scanningTarget` from `ScanResult` prop |
| **RedFlagsList** | `entrypoints/sidepanel/components/scan/RedFlagsList.tsx` | Renders correct number of `RedFlagCard` children; shows "CRITICAL" badge when `critical` is true |
| **RedFlagCard** | `entrypoints/sidepanel/components/scan/RedFlagCard.tsx` | Renders flag `title`, `description`, and icon |
| **ScanActions** | `entrypoints/sidepanel/components/scan/ScanActions.tsx` | Toggle state for auto-scan checkbox; busy state disables re-scan button and shows busy label; `onRescan` callback fires |
| **MatchScoreCard** | `entrypoints/sidepanel/components/match/MatchScoreCard.tsx` | Renders score percentage, compatibility label; progress bar width matches score; renders `SkillGapList` |
| **SkillGapList** | `entrypoints/sidepanel/components/match/SkillGapList.tsx` | Renders correct number of skill gap items; `onAdd` callback fires with gap id |
| **KeywordList** | `entrypoints/sidepanel/components/match/KeywordList.tsx` | Renders keyword labels; shows check icon for `matched: true` items |
| **ResumeCard** | `entrypoints/sidepanel/components/match/ResumeCard.tsx` | Renders filename and lastUpdated; edit button calls `onEdit` |
| **ApplyButton** | `entrypoints/sidepanel/components/match/ApplyButton.tsx` | Renders label text; `onClick` fires on click |
| **TopAppBar** | `entrypoints/sidepanel/components/shell/TopAppBar.tsx` | Renders brand text; help/settings clicks fire callbacks |
| **SideNav** | `entrypoints/sidepanel/components/shell/SideNav.tsx` | Highlights active tab; tab click fires `onTabClick` with correct `ViewId` |
| **Footer** | `entrypoints/sidepanel/components/shell/Footer.tsx` | Renders footer links and copyright |

### Integration Tests (High Priority)

| Scenario | What to test |
|----------|--------------|
| **ScamScanView composition** | `entrypoints/sidepanel/views/ScamScanView.tsx` — renders all sub-components with demo data |
| **ResumeMatchView composition** | `entrypoints/sidepanel/views/ResumeMatchView.tsx` — renders all sub-components with demo data |
| **App navigation** | `entrypoints/sidepanel/App.tsx` — tab switch renders correct view; `SideNav` active state matches `activeView` |
| **Popup rendering** | `entrypoints/popup/App.tsx` — renders feature cards and open button |

### Extension Integration Tests (Medium Priority)

| Scenario | What to test |
|----------|--------------|
| **Background script** | `entrypoints/background.ts` — `browser.action.onClicked` listener opens side panel |
| **Content script** | `entrypoints/content.ts` — script runs on matching pages (currently `*://*.google.com/*`) |
| **Side panel open flow** | Popup button → `chrome.sidePanel.open` → side panel renders |
| **WXT configuration** | `wxt.config.ts` — manifest fields, permissions, module setup |

### Data Layer Tests (Medium Priority)

| File | What to test |
|------|--------------|
| `entrypoints/sidepanel/data/content.ts` | Demo data shapes match `ScanResult` and `MatchResult` types; constants are non-empty strings |
| `entrypoints/sidepanel/types/index.ts` | Type correctness (compile-time check via `tsc --noEmit`) |

### E2E Tests (Lower Priority)

| Scenario | What to test |
|----------|--------------|
| Extension loads in Chrome | Side panel opens; popup renders |
| Scan view displays demo data | All red flags, risk gauge, scan actions visible |
| Match view displays demo data | Resume card, match score, keywords, apply button visible |
| Tab navigation | Switching between Scan and Match views works |
| Re-scan button interaction | Shows busy state, resets after timeout |

## Testing Gaps

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| **No test runner installed** | Cannot run any tests | Add Vitest as dev dependency |
| **No component testing library** | Cannot render React components in tests | Add `@testing-library/react` |
| **No DOM environment** | Cannot test React components in Node | Configure Vitest with `jsdom` environment |
| **No test setup file** | No global mocks (e.g., Chrome API, `chrome.sidePanel`) | Create `test/setup.ts` with Chrome API mocks |
| **No test file convention** | Unclear where tests go | Follow co-located pattern: `ComponentName.test.tsx` next to each component |
| **No test script in package.json** | No standard way to run tests | Add `"test": "vitest run"` script |
| **Chrome API not mocked** | Extension APIs unavailable in test environment | Use `vitest-chrome` or manual `vi.mock('webextension-polyfill')` |
| **No CI pipeline** | Tests never run automatically | Add GitHub Actions workflow with `vitest run` step |
| **No coverage requirements** | No visibility into untested code | Add `c8` or Vitest built-in coverage with 80%+ target |
| **No `data-testid` attributes** | Tests must rely on text content or class selectors (fragile) | Add `data-testid` attributes to interactive elements |
| **No accessible role/label patterns** | Component queries lack reliable selectors | Use semantic HTML (`<button>`, `<nav>`, `<section>`) consistently |
| **Content script has placeholder logic** | `content.ts` only logs "Hello content." — tests would be trivial until real logic is added | Add real content extraction, then test |
| **Background script has `@ts-ignore`** | Test environment may need explicit `chrome.sidePanel` mock | Mock `chrome.sidePanel.open` in test setup |

---

*Testing analysis: 2026-07-05*
