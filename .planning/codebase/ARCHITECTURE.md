<!-- refreshed: 2026-07-05 -->
# Architecture

**Analysis Date:** 2026-07-05

## Overview

Trabahero is a **WXT-based Chrome Extension (MV3)** for AI-powered job scam detection and resume matching targeted at Filipino job seekers. The architecture follows a **three-entrypoint model** mandated by WXT: a background service worker (`background.ts`), a popup (`popup/`), and a side panel (`sidepanel/`). The side panel is the primary UI surface, organized as a single-page React app with component-based view routing driven by local `useState`. Currently the entire application uses hardcoded demo data with no external API calls or persistent state — all data flows from static data modules directly into React components.

The extension uses a **dark theme** (background `#121317`, gold secondary `#e9c349`) defined in `tailwind.config.js` and `assets/tailwind.css`. Despite the design spec in `design/design.md` describing a "Sentinel Path" light theme with Sapphire Blue primary, the actual implementation uses an inverted dark palette with neutral silver surfaces and gold accents.

## Entrypoints

| Entrypoint | File | WXT Type | Role |
|---|---|---|---|
| Background | `entrypoints/background.ts` | `defineBackground` | Service worker; opens Chrome side panel on extension action click via `chrome.sidePanel.open()` |
| Popup | `entrypoints/popup/main.tsx` | `defineUnlistedScript` (via HTML) | 320px-wide popup displayed on toolbar icon click; shows brand header, two feature cards (Scam Scan, Resume Match), and a footer |
| Side Panel | `entrypoints/sidepanel/main.tsx` | `defineUnlistedScript` (via HTML) | Full-height side panel (opened by background); main application shell with routing |
| Content Script | `entrypoints/content.ts` | `defineContentScript` | Placeholder; matches `*://*.google.com/*`, logs `"Hello content."` — currently no DOM interaction |

## Component Tree

```
Popup (entrypoints/popup/App.tsx)
├── PopupIcon (inline component)
├── Header — brand text "Trabahero" + launch icon
├── Main
│   ├── Description text
│   ├── "Open Trabahero" primary button
│   └── Two feature cards (Scam Scan / Resume Match)
└── Footer — copyright line

Side Panel (entrypoints/sidepanel/App.tsx)
├── TopAppBar (components/shell/TopAppBar.tsx)
│   ├── Brand text "Trabahero" (gold gradient)
│   └── Help + Settings icon buttons
├── Shell layout (flex row)
│   ├── SideNav (components/shell/SideNav.tsx)
│   │   ├── NAV_TABS — Scan / Match tab buttons
│   │   └── BOTTOM_NAV_ICONS — support / external icons
│   └── Main Content Area (switched by activeView)
│       ├── ScamScanView (views/ScamScanView.tsx)
│       │   ├── SecurityBanner (components/scan/SecurityBanner.tsx)
│       │   ├── RiskGauge (components/scan/RiskGauge.tsx)
│       │   ├── RedFlagsList (components/scan/RedFlagsList.tsx)
│       │   │   └── RedFlagCard × N (components/scan/RedFlagCard.tsx)
│       │   └── ScanActions (components/scan/ScanActions.tsx)
│       └── ResumeMatchView (views/ResumeMatchView.tsx)
│           ├── ResumeCard (components/match/ResumeCard.tsx)
│           ├── MatchScoreCard (components/match/MatchScoreCard.tsx)
│           │   └── SkillGapList (components/match/SkillGapList.tsx)
│           ├── KeywordList (components/match/KeywordList.tsx)
│           ├── ApplyButton (components/match/ApplyButton.tsx)
│           └── MatchFooter (components/match/MatchFooter.tsx)
└── Footer (components/shell/Footer.tsx)
    ├── Legal + Privacy links
    └── Copyright line
```

## Data Flow

1. **Demo data entry point:** `entrypoints/sidepanel/data/content.ts` exports `SCAN_RESULT_DEMO` and `MATCH_RESULT_DEMO` as well as label strings, nav tab definitions, and footer link data.

2. **View layer receives data:** Each view (`ScamScanView.tsx`, `ResumeMatchView.tsx`) accepts an optional `result` prop that defaults to the demo data:
   ```tsx
   // ScamScanView.tsx
   export function ScamScanView({ result = SCAN_RESULT_DEMO, ... })
   ```

3. **Components consume slices:** Each child component receives only the specific props it needs (e.g., `RiskGauge` gets `score` and `description`, `KeywordList` gets `keywords` array).

4. **Event callbacks bubble up:** Action components (`ScanActions`, `ApplyButton`) accept optional callback props (`onRescan`, `onReport`, `onApply`, `onEditResume`, `onAddGap`) that currently do nothing — the callbacks are never wired in `App.tsx`.

5. **Data never leaves the client:** No `fetch()`, `chrome.storage`, `browser.runtime.sendMessage`, or any persistence. All state is local `useState` in `App.tsx` (for `activeView`) and `ScanActions.tsx` (for `autoScan` toggle + `busy` rescan state).

```
Demo Data (data/content.ts)
    │
    ▼
View Composer (views/ScamScanView.tsx or ResumeMatchView.tsx)
    │
    ├──► prop drilling ──► Presentational Components
    │                       (read props, render UI)
    └──► callback props ──► Action Components
                            (onRescan, onReport, etc. — currently stubs)
```

## Routing / Navigation

Routing is **component-based, not URL-based**. `entrypoints/sidepanel/App.tsx` holds a `useState<ViewId>('scan')` that toggles between two views:

```tsx
const [activeView, setActiveView] = useState<ViewId>('scan');
// ...
{activeView === 'scan' ? <ScamScanView /> : <ResumeMatchView />}
```

The `SideNav` component renders `NAV_TABS` (Scan / Match) from `data/content.ts` and calls `onTabClick` (which is `setActiveView`) when a tab is pressed. Active styling uses the `.nav-item-active` CSS class (gold gradient background + tactile shadow).

The popup has no routing — it is a single, static 320px view with a "Open Trabahero" button that triggers `chrome.sidePanel.open()` and closes the popup.

## State Management

**No global state management.** The application uses only React local state:

- `App.tsx` — `useState<ViewId>('scan')` for active nav tab
- `ScanActions.tsx` — `useState(autoScanDefault)` for auto-scan toggle
- `ScanActions.tsx` — `useState(false)` for rescan busy/loading indicator

All component props are passed down as either **data props** (read-only values from demo data) or **callback props** (event handlers — none wired to actual logic yet).

There is no `useContext`, no `useReducer`, no external state library (Redux, Zustand, etc.), and no cross-entrypoint messaging (`runtime.sendMessage`).

## Key Design Decisions

1. **Side panel as primary surface:** The popup is intentionally minimal (branding + feature cards + launch button). All substantive UI lives in the Chrome side panel, which persists across page navigations and provides more screen real estate (420px+ vs 320px popup).

2. **WXT with React module:** `wxt.config.ts` selects `@wxt-dev/module-react` for automatic JSX/TSX handling, avoiding manual Vite React plugin configuration.

3. **Dark theme with gold accents:** The implementation uses a dark Material 3-inspired palette (neutral silver surfaces, gold secondary, red error) rather than the light Sapphire Blue theme described in `design/design.md`. This dark theme is defined in `tailwind.config.js` under `theme.extend.colors`.

4. **Demo data before backend:** The project started building the UI layer with hardcoded demo data (`data/content.ts`). This allows visual development and user testing before the scam-detection AI and resume-matching backend are integrated.

5. **Prop drilling over context:** With only 2 views and 1 level of nesting, there is no state management or context API. All data flows through props. This is appropriate for the current scale but would need `useContext` or a store if views or data sources grow.

6. **Barrel index files:** Each component subdirectory (`scan/`, `match/`, `shell/`, `common/`) has an `index.ts` that re-exports its components — a standard pattern for clean imports.

7. **Content script is a placeholder:** `entrypoints/content.ts` matches `google.com` but does nothing. It is ready for future DOM scraping of job listings from Google search results.

8. **ScanActions has internal busy simulation:** The rescan button simulates a 2-second busy state with a `setTimeout` — this is a UX placeholder for future real scan API calls.

## Layers

**Data Layer:**
- Purpose: Provides hardcoded demo data and label strings
- Location: `entrypoints/sidepanel/data/content.ts`
- Contains: `SCAN_RESULT_DEMO`, `MATCH_RESULT_DEMO`, `NAV_TABS`, `FOOTER_LINKS`, label constants
- Depends on: `types/index.ts` for type annotations
- Used by: View composers (`views/`) and some shell components

**Type Layer:**
- Purpose: Defines TypeScript interfaces and type aliases shared across the side panel
- Location: `entrypoints/sidepanel/types/index.ts`
- Contains: `ViewId`, `ScanResult`, `MatchResult`, `RedFlag`, `SkillGap`, `MatchKeyword`, `NavTab`, `IconName`
- Used by: All views, components, and data modules

**View Layer:**
- Purpose: Composes presentational and action components into feature views; provides default data injection
- Location: `entrypoints/sidepanel/views/`
- Contains: `ScamScanView.tsx`, `ResumeMatchView.tsx`
- Depends on: Data layer, component layer
- Used by: `App.tsx` (conditional rendering)

**Component Layer:**
- Purpose: Presentational and interactive UI components, organized by feature
- Location: `entrypoints/sidepanel/components/{common,shell,scan,match}/`
- Contains: Reusable components like `Icon`, `TopAppBar`, `SideNav`, `RiskGauge`, `RedFlagCard`, `KeywordList`, etc.
- Depends on: Types layer, `data/content.ts` (for labels), `common/Icon`

**Shell Layer:**
- Purpose: Application chrome — top bar, navigation, and footer that persist across view changes
- Location: `entrypoints/sidepanel/components/shell/`
- Contains: `TopAppBar`, `SideNav`, `Footer`
- Used by: `App.tsx` only

## Data Flow Diagram

```
                   ┌──────────────────┐
                   │  background.ts   │
                   │  (service worker)│
                   └────────┬─────────┘
                            │ onClick
                            ▼
                   ┌──────────────────┐
                   │ chrome.sidePanel │
                   │ .open()          │
                   └────────┬─────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                                      ▼
┌──────────────────┐                  ┌──────────────────┐
│   Popup (320px)  │                  │  Side Panel      │
│  popup/main.tsx  │                  │ sidepanel/main.ts│
│  (opens sidepanel│                  │                  │
│   then closes)   │                  │ App.tsx           │
└──────────────────┘                  │  │               │
                                      │  │ useState      │
                                      │  │ ViewId         │
                                      │  ▼               │
                                      │ ┌────────────┐   │
                                      │ │  TopAppBar  │   │
                                      │ ├────────────┤   │
                                      │ │ SideNav     │   │
                                      │ ├─────┬──────┤   │
                                      │ │Scan │Match │   │
                                      │ │View │ View │   │
                                      │ ├─────┴──────┤   │
                                      │ │  Footer     │   │
                                      │ └────────────┘   │
                                      └──────────────────┘
```

## Anti-Patterns

### Unwired Callback Props

**What happens:** `App.tsx` passes no `onRescan`, `onReport`, `onApply`, `onEditResume`, or `onAddGap` callbacks. These props are accepted by child components but never invoked.

**Why it's wrong:** Half the interactive elements (report button, edit resume, add skill gap, apply button) are non-functional dead ends. The rescan button in `ScanActions.tsx` simulates a 2-second busy state but triggers no real action.

**Do this instead:** Either wire callbacks to `chrome.runtime.sendMessage`, `chrome.storage`, or an API call, or make the components only render when the callbacks are provided (conditional rendering).

### Demo Data Injected as Default Prop

**What happens:** Both `ScamScanView` and `ResumeMatchView` hardcode `result = SCAN_RESULT_DEMO` / `result = MATCH_RESULT_DEMO` as default parameter values.

**Why it's wrong:** The default prop pattern silently masks the absence of real data. When the callbacks are eventually wired to fetch live data, the default value will create confusing behavior (demo data showing before API response arrives).

**Do this instead:** Use `null` or `undefined` as the initial value and render a loading state. The demo data should only appear in Storybook or dev mode, not in production code paths.

---

*Architecture analysis: 2026-07-05*
