# Integrations

**Analysis Date:** 2026-07-05

## Browser APIs

| API | Used In | Purpose |
|-----|---------|---------|
| `chrome.sidePanel.open()` | `entrypoints/background.ts` (line 6), `entrypoints/popup/App.tsx` (line 29) | Opens the side panel when the extension action button is clicked or when the popup's "Open Trabahero" button is pressed |
| `browser.action.onClicked` | `entrypoints/background.ts` (line 3) | Listens for the extension toolbar icon click to trigger side panel open |
| `browser.tabs.query` | `entrypoints/popup/App.tsx` (line 26) | Gets the active tab to pass `tabId` when opening the side panel |
| `storage` | Manifest permission declared in `wxt.config.ts` | Available for future use — not yet implemented |
| `activeTab` | Manifest permission declared | Available for future content script interactions |
| `tabs` | Manifest permission declared | Available for future tab-management features |

## External Services / APIs

| Service | Status | Details |
|---------|--------|---------|
| **Google Fonts** | Active (runtime) | **Hanken Grotesk** (headline font) and **Inter** (body/label font) loaded via external stylesheet. Defined in `tailwind.config.js` under `fontFamily` |
| **Material Symbols Outlined** | Active (runtime) | Icon font used extensively across the popup and sidepanel UI. Icons referenced by name in `entrypoints/sidepanel/types/index.ts` (`IconName` type) and rendered via `<Icon>` component in `entrypoints/sidepanel/components/common/Icon.tsx` |
| **Stitch by Google** | Developer tool only | MCP integration in `opencode.json` for AI-driven design system generation. Used during development, not shipped with the extension |
| **Localhost backend** | Planned / not implemented | Host permission `http://localhost:8000/*` declared in `wxt.config.ts` but no source code references it. Likely a future ML/AI inference server endpoint |
| **External scam-detection API** | Not yet integrated | No external API calls exist. All scam scan data is hardcoded demo data in `entrypoints/sidepanel/data/content.ts` |
| **External resume-matching API** | Not yet integrated | All resume match data is hardcoded demo data (`MATCH_RESULT_DEMO`) in `entrypoints/sidepanel/data/content.ts` |

## Third-Party Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `react` | ^19.2.4 | UI component framework |
| `react-dom` | ^19.2.4 | React DOM renderer |
| `wxt` | ^0.20.27 | Extension build framework |
| `@wxt-dev/module-react` | ^1.1.5 | WXT module for React integration |
| `tailwindcss` | ^3.4.17 | Utility-first CSS framework |
| `postcss` | ^8.5.6 | CSS post-processing |
| `autoprefixer` | ^10.4.21 | CSS vendor prefixing |
| `typescript` | ^5.9.3 | Type checking and compilation |

## Data Flow

```
User clicks extension icon
        │
        ▼
background.ts ──► chrome.sidePanel.open(tabId)
        │
        ▼
popup/App.tsx  ──► "Open Trabahero" button ──► chrome.sidePanel.open(tabId)
        │
        ▼
sidepanel/App.tsx
   ├── ScamScanView (default view)
   │     └── data/content.ts (SCAN_RESULT_DEMO — hardcoded)
   └── ResumeMatchView
         └── data/content.ts (MATCH_RESULT_DEMO — hardcoded)
```

**Current state:** The data flow is entirely client-side and synchronous. No data is fetched from or sent to external servers. The extension views render hardcoded demo objects directly from `entrypoints/sidepanel/data/content.ts`. User interactions (rescan, report, apply) have placeholder callbacks with no implementation.

**Future state (inferred from permissions):**
1. Content script on `*://*.google.com/*` could extract job listing data
2. Data would be sent to `http://localhost:8000/*` (ML inference server)
3. Results would be stored via `storage` API and rendered in the sidepanel

## Known Integration Gaps

1. **No ML/AI inference integration.** Despite the project description ("AI-powered job scam detection"), no AI model or API is connected. The `http://localhost:8000/*` permission suggests a local inference server was planned but not implemented.

2. **Content script is a stub.** `entrypoints/content.ts` only targets `*://*.google.com/*` and logs "Hello content." No page data extraction, DOM analysis, or messaging to the background/sidepanel exists.

3. **No storage integration.** The `storage` permission is declared but no `chrome.storage` calls exist anywhere in the codebase. User preferences, scan history, and cached results are not persisted.

4. **No messaging layer.** There is no `chrome.runtime.sendMessage` / `chrome.runtime.onMessage` communication between the content script, background, and sidepanel. The architecture has all the pieces but no inter-script communication.

5. **No error tracking or analytics.** No Sentry, Google Analytics, or similar monitoring integration.

6. **No CI/CD deployment pipeline.** Browser Web Store publishing workflows are not configured.

---

*Integration audit: 2026-07-05*
