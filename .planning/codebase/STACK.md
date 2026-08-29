# Stack

**Analysis Date:** 2026-07-05

## Languages

- **TypeScript** ^5.9.3 — Primary language for all extension code (background, content script, popup, sidepanel)
- **CSS** — Custom styling via Tailwind utility classes; design tokens defined in `tailwind.config.js`

## Frameworks & Runtimes

- **WXT** ^0.20.27 — Build tool and extension framework; handles manifest generation, HMR dev server, and bundling for Chrome/Firefox. Config: `wxt.config.ts`
- **React** ^19.2.4 — UI framework used for popup (`entrypoints/popup/App.tsx`) and side panel (`entrypoints/sidepanel/App.tsx`). Uses `react-jsx` transform.
- **Chrome Extension MV3** — Extension architecture target. Manifest V3 with `sidePanel` API. Permissions: `activeTab`, `storage`, `tabs`, `sidePanel`, `<all_urls>`, `http://localhost:8000/*`

## Build & Dev Tooling

- **WXT** ^0.20.27 — Dev server (`wxt`), build (`wxt build`), zip (`wxt zip`). Supports `-b firefox` flag for cross-browser builds. Postinstall hook: `wxt prepare`
- **TypeScript** ^5.9.3 — Type checking via `tsc --noEmit` (`compile` script). Config extends auto-generated `.wxt/tsconfig.json` with `react-jsx` JSX mode
- **@wxt-dev/module-react** ^1.1.5 — WXT module that wires up React support (HMR, JSX handling)

## UI / Styling

- **React** ^19.2.4 — Component library for popup and sidepanel views
- **Tailwind CSS** ^3.4.17 — Utility-first CSS framework. Config: `tailwind.config.js`
- **PostCSS** ^8.5.6 — CSS post-processor. Config: `postcss.config.js`
- **Autoprefixer** ^10.4.21 — Vendor prefix insertion
- **Google Fonts** — **Hanken Grotesk** (headlines) and **Inter** (body/label) loaded at runtime via external link
- **Material Symbols Outlined** — Icon font used throughout the UI (security, description, warning, etc.)
- **Design System: "Sentinel Path"** — Full custom dark theme defined in `tailwind.config.js`. Features:
  - Dark-only mode (`darkMode: 'class'`)
  - Custom color palette: surface (dark neutral), primary (silver), secondary (Vigilance Yellow/gold), error (red)
  - Typography scale: `headline-xl` through `label-sm` with specific weights, letter-spacing, and line-height
  - Custom spacing tokens: `compact` (4px) through `gutter` (24px)
  - Custom animations: `spin-once`, `pulse-ring` (gold glow), `slide-in`
  - Tactile 3D shadows: `tactile`, `tactile-gold`, `tactile-active`, `card`
  - Custom border radii: `sm` (2px) through `full` (9999px)

## Backend / Data

- **No external backend or database configured.** All data is currently client-side demo/stub data:
  - `entrypoints/sidepanel/data/content.ts` — Hardcoded `SCAN_RESULT_DEMO` and `MATCH_RESULT_DEMO` objects
- **`storage` permission declared** in manifest (available but not yet used in source files)
- **`http://localhost:8000/*` host permission** declared — suggests a planned local development backend at port 8000, but no code references it yet

## Testing

- **None configured.** No test runner, no test files, no test scripts in `package.json`. No `jest.config.*`, `vitest.config.*`, or similar files exist.

## Infrastructure / Deployment

- **No CI/CD configuration found.** No `.github/workflows/`, `.gitlab-ci.yml`, or similar files.
- **Extension distribution:** Not configured. `wxt zip` command available for creating extension packages.
- **Stitch MCP integration** configured in `opencode.json` for design system generation — developer tool only, not shipped with the extension.

---

*Stack analysis: 2026-07-05*
