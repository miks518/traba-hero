# Codebase Structure

**Analysis Date:** 2026-07-05

## Directory Layout

```
trabahero/
├── assets/                            # Static assets loaded by entrypoints
│   ├── react.svg
│   └── tailwind.css                   # Google Fonts import + Tailwind directives + custom component classes
│
├── design/                            # Design system specification (not used at runtime)
│   ├── design.md                      # "Sentinel Path" design system spec (light theme, Sapphire Blue)
│   ├── resume_match.html              # HTML mockup for resume match view
│   ├── scam_scan.html                 # HTML mockup for scam scan view
│   └── theme.json                     # Theme tokens (light mode colors, typography)
│
├── entrypoints/                       # WXT entrypoints — each is a separate extension page/script
│   ├── background.ts                  # Service worker: opens side panel on action click
│   ├── content.ts                     # Content script: placeholder matching google.com
│   ├── popup/                         # Popup entrypoint (320px)
│   │   ├── index.html                 # HTML shell
│   │   ├── main.tsx                   # React DOM entry, imports tailwind.css + style.css
│   │   ├── App.tsx                    # Popup UI: brand header, two feature cards, footer
│   │   ├── style.css                  # Popup-specific styles (body margin, fixed width 320px)
│   │   ├── components/                # (empty — no components extracted yet)
│   │   ├── data/                      # (empty)
│   │   ├── hooks/                     # (empty)
│   │   └── types/                     # (empty)
│   └── sidepanel/                     # Side panel entrypoint (primary UI)
│       ├── index.html                 # HTML shell
│       ├── main.tsx                   # React DOM entry
│       ├── App.tsx                    # Shell with TopAppBar + SideNav + view switching
│       ├── types/
│       │   └── index.ts               # TypeScript interfaces: ViewId, NavTab, RedFlag, ScanResult, etc.
│       ├── data/
│       │   └── content.ts             # Hardcoded demo data and label strings
│       ├── views/
│       │   ├── ScamScanView.tsx       # Composes scan components with SCAN_RESULT_DEMO
│       │   └── ResumeMatchView.tsx    # Composes match components with MATCH_RESULT_DEMO
│       └── components/
│           ├── common/
│           │   ├── index.ts           # Barrel re-export
│           │   └── Icon.tsx           # Material Symbols Outlined icon wrapper
│           ├── shell/
│           │   ├── index.ts           # Barrel re-export
│           │   ├── TopAppBar.tsx      # Header with brand text, help/settings icons
│           │   ├── SideNav.tsx        # Vertical nav with scan/match tabs + bottom icons
│           │   └── Footer.tsx         # Legal/privacy links + copyright
│           ├── scan/
│           │   ├── index.ts           # Barrel re-export
│           │   ├── SecurityBanner.tsx # Error banner showing scan status
│           │   ├── RiskGauge.tsx      # SVG circular gauge (gold gradient) showing risk score
│           │   ├── RedFlagCard.tsx    # Individual red flag card with icon + title + description
│           │   ├── RedFlagsList.tsx   # List of RedFlagCards with CRITICAL badge
│           │   └── ScanActions.tsx    # Auto-scan toggle, rescan button (with busy state), report button
│           └── match/
│               ├── index.ts           # Barrel re-export
│               ├── ResumeCard.tsx     # Resume file info with edit button
│               ├── MatchScoreCard.tsx # Score display with skill gaps
│               ├── SkillGapList.tsx   # List of skill gap chips with add button
│               ├── KeywordList.tsx    # Matched keyword list
│               ├── ApplyButton.tsx    # Apply action button
│               └── MatchFooter.tsx    # Footer for match view
│
├── public/                            # Extension static assets (copied to dist root)
│   └── icon/                          # Extension icons (16, 32, 48, 96, 128 PNGs)
│       ├── 16.png
│       ├── 32.png
│       ├── 48.png
│       ├── 96.png
│       └── 128.png
│
├── .planning/                         # Project planning documents (auto-generated)
│   └── codebase/                      # Codebase analysis documents
│
├── package.json                       # Dependencies: react 19, react-dom 19, wxt 0.20, tailwindcss 3.4
├── package-lock.json
├── wxt.config.ts                      # WXT config: manifest, permissions, side_panel path, module-react
├── tsconfig.json                      # TypeScript configuration
├── tailwind.config.js                 # Tailwind theme: dark mode colors, typography scale, spacing, keyframes
├── postcss.config.js                  # PostCSS config (Tailwind + autoprefixer)
└── opencode.json                      # OpenCode configuration
```

## Module Responsibilities

| Path | Responsibility |
|------|----------------|
| `entrypoints/background.ts` | Opens the Chrome side panel when the extension toolbar icon is clicked |
| `entrypoints/content.ts` | Placeholder content script matching `google.com` for future DOM scraping |
| `entrypoints/popup/App.tsx` | Renders 320px popup with brand, feature cards, and open-panel action |
| `entrypoints/popup/style.css` | Sets body margin to 0 and popup width to 320px |
| `entrypoints/sidepanel/App.tsx` | Root shell component that composes TopAppBar, SideNav, view routing, and Footer |
| `entrypoints/sidepanel/main.tsx` | React DOM mount point for side panel, imports `tailwind.css` |
| `entrypoints/sidepanel/types/index.ts` | All TypeScript type definitions for the side panel domain model |
| `entrypoints/sidepanel/data/content.ts` | Demo data (`SCAN_RESULT_DEMO`, `MATCH_RESULT_DEMO`), nav definitions, label strings |
| `entrypoints/sidepanel/components/common/Icon.tsx` | Reusable Material Symbols Outlined icon component with FILL variation support |
| `entrypoints/sidepanel/components/shell/TopAppBar.tsx` | Top header bar with brand text and help/settings icons |
| `entrypoints/sidepanel/components/shell/SideNav.tsx` | Left vertical navigation with Scan/Match tabs and bottom action icons |
| `entrypoints/sidepanel/components/shell/Footer.tsx` | Application footer with Legal/Privacy links and copyright |
| `entrypoints/sidepanel/components/scan/SecurityBanner.tsx` | High-visibility error banner showing scan status title and target |
| `entrypoints/sidepanel/components/scan/RiskGauge.tsx` | SVG circular progress gauge showing risk score with gold gradient |
| `entrypoints/sidepanel/components/scan/RedFlagCard.tsx` | Single red flag card with icon, title, and description |
| `entrypoints/sidepanel/components/scan/RedFlagsList.tsx` | Ordered list of `RedFlagCard` components with optional CRITICAL badge |
| `entrypoints/sidepanel/components/scan/ScanActions.tsx` | Auto-scan toggle switch, rescan button (with busy animation), report button |
| `entrypoints/sidepanel/components/match/ResumeCard.tsx` | Displays active resume filename, last-updated date, and edit button |
| `entrypoints/sidepanel/components/match/MatchScoreCard.tsx` | Score percentage, compatibility label, progress bar, and `SkillGapList` |
| `entrypoints/sidepanel/components/match/SkillGapList.tsx` | Clickable skill gap chips with add icon |
| `entrypoints/sidepanel/components/match/KeywordList.tsx` | Top-matched keywords list with check-circle icons |
| `entrypoints/sidepanel/components/match/ApplyButton.tsx` | Primary gold "Apply with Match" action button |
| `entrypoints/sidepanel/components/match/MatchFooter.tsx` | Footer for match view with Legal/Privacy links and copyright |
| `assets/tailwind.css` | Font imports (Hanken Grotesk, Inter, Material Symbols), Tailwind directives, custom component classes (`.tactile-card`, `.tactile-btn-gold`, `.nav-item-active`, `.text-gold-gradient`) |
| `tailwind.config.js` | Full Material 3-inspired dark theme: color palette, typography scale (headline-xl through label-sm), spacing, animations, box shadows |

## File Naming Conventions

| Convention | Description | Examples |
|------------|-------------|----------|
| **PascalCase.tsx** | React component files | `TopAppBar.tsx`, `RedFlagCard.tsx`, `RiskGauge.tsx` |
| **camelCase.ts** | Non-component TypeScript modules | `background.ts`, `content.ts`, `tailwind.config.js` |
| **lowercase.md** | Documentation files | `design.md` |
| **index.ts** | Barrel re-exports for component directories | `sidepanel/components/scan/index.ts` |
| **Component names match filenames** | Each file exports a single component named after the file | `TopAppBar.tsx` exports `TopAppBar`, `RiskGauge.tsx` exports `RiskGauge` |
| **Feature-based directory grouping** | Components organized by feature (scan/match), not by type | `components/scan/`, `components/match/` |

## Entry Points

| Entry Point | File | What It Initializes |
|-------------|------|---------------------|
| Service Worker | `entrypoints/background.ts` | `defineBackground` — adds `browser.action.onClicked` listener that calls `chrome.sidePanel.open()` |
| Content Script | `entrypoints/content.ts` | `defineContentScript` — matches `google.com`, logs `"Hello content."` (placeholder) |
| Popup | `entrypoints/popup/main.tsx` | Mounts React root at `#root`, imports `tailwind.css` + `style.css`, renders `App` (Popup) |
| Side Panel | `entrypoints/sidepanel/main.tsx` | Mounts React root at `#root`, imports `tailwind.css`, renders `App` (side panel shell) |

## Where to Add New Code

**New feature view (e.g., "History", "Settings"):**
1. Add view ID to `ViewId` union type in `entrypoints/sidepanel/types/index.ts`
2. Add nav tab entry to `NAV_TABS` in `entrypoints/sidepanel/data/content.ts`
3. Create view composer in `entrypoints/sidepanel/views/` (e.g., `HistoryView.tsx`)
4. Create any new components under `entrypoints/sidepanel/components/<feature>/`
5. Add conditional rendering in `entrypoints/sidepanel/App.tsx`
6. `SideNav.tsx` will automatically render the new tab from `NAV_TABS`

**New shared component:**
- Create file under `entrypoints/sidepanel/components/common/` (e.g., `Button.tsx`)
- Add barrel export to `entrypoints/sidepanel/components/common/index.ts`

**New feature component group:**
- Create new directory under `entrypoints/sidepanel/components/` (e.g., `history/`)
- Add components with PascalCase filenames
- Create `index.ts` barrel re-export

**Real API integration (replacing demo data):**
- Replace default parameter values in view files (`ScamScanView.tsx`, `ResumeMatchView.tsx`) with `undefined` or loading state
- Wire callback props in `App.tsx` to actual `chrome.runtime.sendMessage()` or `fetch()` calls
- Consider adding a service layer at `entrypoints/sidepanel/services/` for API calls
- Add loading/error states to components that currently assume data is always available

**Changing the popup:**
- Popup components currently live inline in `entrypoints/popup/App.tsx`. Extract reusable components to `entrypoints/popup/components/` if the popup grows.

## Special Directories

| Directory | Purpose | Generated | Committed |
|-----------|---------|-----------|-----------|
| `public/icon/` | Extension icons referenced by the manifest | No | Yes |
| `design/` | Design specification files (design.md, HTML mockups, theme.json) | No | Yes |
| `assets/` | Static assets loaded at build time (CSS, SVGs) | No | Yes |
| `.planning/` | Auto-generated planning documents | Yes | Yes |

---

*Structure analysis: 2026-07-05*
