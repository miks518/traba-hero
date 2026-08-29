# Conventions

## Code Style

- **Language:** TypeScript 5.9 with strict mode enabled (via `.wxt/tsconfig.json` extension); `jsx: "react-jsx"` transform in `tsconfig.json`
- **React version:** React 19.2.4 with React DOM 19.2.4
- **Formatting:** No Prettier config detected — formatting is unenforced
- **Linting:** No ESLint, Biome, or any linter config detected — no automated code quality enforcement
- **Indentation:** Default editor settings (inferred as 2-space based on `postcss.config.js` style) with no `.editorconfig`
- **CSS approach:** Tailwind utility classes with custom layer components via `@layer components` in `assets/tailwind.css`
- **3D tactile effects:** Custom `box-shadow` tokens (`shadow-tactile`, `shadow-tactile-gold`, `shadow-tactile-active`, `shadow-card`) and CSS classes (`.tactile-card`, `.tactile-btn-gold`, `.btn-outline-gold`) used for interactive elements
- **TypeScript strictness:** `@ts-ignore` comments used sparingly for Chrome extension APIs not in WXT's type defs (e.g., `chrome.sidePanel.open`)

## Naming Conventions

| Category | Convention | Examples |
|---|---|---|
| **Files (components)** | PascalCase `.tsx` | `TopAppBar.tsx`, `RedFlagCard.tsx`, `MatchScoreCard.tsx` |
| **Files (data/types/entry)** | camelCase `.ts`/`.tsx` | `content.ts`, `background.ts`, `main.tsx` |
| **Files (shell entry)** | kebab-case | `index.html`, `index.ts` (barrel) |
| **Components (exported)** | PascalCase named function | `export function SecurityBanner(...)` |
| **Default exports** | PascalCase, same as named | `export default SecurityBanner` |
| **Props interfaces** | PascalCase with `Props` suffix | `SecurityBannerProps`, `ScanActionsProps` |
| **Variables/functions** | camelCase | `activeView`, `setActiveView`, `handleRescan`, `openSidepanel` |
| **Constants** | SCREAMING_SNAKE_CASE | `AUTO_SCAN_LABEL`, `RESCAN_LABEL`, `FOOTER_LINKS`, `NAV_TABS` |
| **Types** | PascalCase | `ScanResult`, `RedFlag`, `MatchResult`, `ViewId` |
| **Icon names** | snake_case (Material Symbols convention) | `'check_circle'`, `'rocket_launch'`, `'phone_disabled'` |
| **CSS classes** | kebab-case | `tactile-card`, `btn-outline-gold`, `text-gold-gradient`, `custom-scroll` |

## Component Patterns

- **Function components with explicit props interface:**
  Every component declares a co-located `export interface ComponentNameProps` immediately before the function definition.
  ```tsx
  // entrypoints/sidepanel/components/scan/RedFlagCard.tsx
  export interface RedFlagCardProps {
    flag: RedFlag;
  }

  export function RedFlagCard({ flag }: RedFlagCardProps) {
    // ...
  }
  ```

- **Dual export pattern:** Every component exports both a named function AND a default export:
  ```tsx
  export function TopAppBar({ ... }: TopAppBarProps) { ... }
  export default TopAppBar;
  ```

- **Default props via destructuring defaults:**
  ```tsx
  export function ApplyButton({ label = APPLY_LABEL, onClick }: ApplyButtonProps) {
  ```

- **Simple state management with `useState`, no external state libraries:**
  ```tsx
  // ScanActions.tsx
  const [autoScan, setAutoScan] = useState(autoScanDefault);
  const [busy, setBusy] = useState(false);
  ```

- **No `React.FC` usage:** Components use plain function syntax with typed destructured props.

- **No custom hooks extracted:** All state logic is inline in components (e.g., `handleRescan` in `ScanActions.tsx`).

- **View components compose sub-components through barrel imports:**
  ```tsx
  import { SecurityBanner, RiskGauge, RedFlagsList, ScanActions } from '../components/scan';
  ```

## Imports & Exports

- **React import always present:** Every `.tsx` file starts with `import React from 'react';` (even when not strictly needed post-React 19).
- **Relative imports only:** No path aliases configured; all imports use relative paths from the importing file.
- **Barrel exports via `index.ts`:** Each component subdirectory has an `index.ts` that re-exports named members:
  ```tsx
  // entrypoints/sidepanel/components/scan/index.ts
  export { SecurityBanner } from './SecurityBanner';
  export { RiskGauge } from './RiskGauge';
  export { RedFlagsList } from './RedFlagsList';
  export { RedFlagCard } from './RedFlagCard';
  export { ScanActions } from './ScanActions';
  ```
- **Type imports use `import type` syntax** for type-only imports:
  ```tsx
  import type { ScanResult, RedFlag } from '../../types';
  ```
- **CSS imports** use direct relative paths to `assets/tailwind.css`:
  ```tsx
  import '../../assets/tailwind.css';
  ```
- **Co-located `Icon.tsx` re-exports its own `IconName` type** — the `types/index.ts` also defines a `IconName` type that mirrors it (duplicate).

## Styling Approach

- **Tailwind CSS v3.4.17** with custom config in `tailwind.config.js`.
- **Custom design tokens** defined under `theme.extend`:
  - `colors`: Full Material 3-like surface/primary/secondary/error scale with Filipino-designer-appropriate gold (secondary) and dark theme defaults
  - `fontFamily`: `'headline'` (Hanken Grotesk), `'body'` (Inter), `'label'` (Inter)
  - `fontSize`: Semantic scale `'headline-xl'` through `'label-sm'`
  - `borderRadius`: `'sm'` through `'full'` with explicit rem values
  - `spacing`: Semantic tokens `'container-padding'`, `'stack-gap'`, `'section-margin'`, `'inline-gap'`, etc.
  - `boxShadow`: `'tactile'`, `'tactile-gold'`, `'tactile-active'`, `'card'` for 3D pressable effect
  - `keyframes`/`animation`: `'spin-once'`, `'pulse-ring'`, `'slide-in'`
- **Dark mode only:** `darkMode: 'class'` set but all tokens are dark-toned; no light theme tokens exist.
- **Custom CSS layers in `assets/tailwind.css`:**
  - `@layer base`: Google Fonts import, Material Symbols import, body defaults, Material Symbols base style
  - `@layer components`: `.tactile-card`, `.tactile-btn-gold` (and `:active` state), `.btn-outline-gold`, `.custom-scroll`, `.text-gold-gradient`, `.nav-item-active`
- **Inline `style` props** used sparingly for dynamic values (e.g., SVG stroke-dashoffset in `RiskGauge.tsx`, progress bar width in `MatchScoreCard.tsx`).
- **No CSS modules or CSS-in-JS** — all styling is Tailwind utilities + custom component layer classes.

## TypeScript Usage

- **Interfaces over types:** Props are always `interface`, domain models are `interface`:
  ```tsx
  export interface ScanResult { ... }
  export interface IconProps extends React.HTMLAttributes<HTMLSpanElement> { ... }
  ```
- **Type alias for unions:** `ViewId` is a union type alias:
  ```tsx
  export type ViewId = 'scan' | 'match';
  ```
- **Duplicated type definition:** `IconName` is defined both in `entrypoints/sidepanel/types/index.ts` and `entrypoints/sidepanel/components/common/Icon.tsx` — they are identical but not shared/imported between files.
- **No generics used** in any component or utility.
- **No `enum` usage** — all enumerations use string union types.
- **`as const` assertions** for readonly data arrays:
  ```tsx
  export const BOTTOM_NAV_ICONS = ['contact_support', 'open_in_new'] as const;
  export const FOOTER_LINKS = [...] as const;
  ```
- **`React.HTMLAttributes<HTMLSpanElement>`** used in `Icon.tsx` for spreading HTML attributes, but `Icon` is the only component that extends HTML attributes.

## File Organization

```
entrypoints/
├── background.ts              # WXT background script (defineBackground)
├── content.ts                 # WXT content script (defineContentScript)
├── popup/
│   ├── App.tsx                # Popup root component
│   ├── main.tsx               # Popup React entry point
│   ├── index.html             # Popup HTML shell
│   └── style.css              # Popup-specific CSS
└── sidepanel/
    ├── App.tsx                # Sidepanel root component
    ├── main.tsx               # Sidepanel React entry point
    ├── index.html             # Sidepanel HTML shell
    ├── types/
    │   └── index.ts           # All domain types and interfaces
    ├── data/
    │   └── content.ts         # Demo data, constants, string labels
    ├── views/
    │   ├── ScamScanView.tsx   # Top-level scan view
    │   └── ResumeMatchView.tsx# Top-level match view
    └── components/
        ├── common/
        │   ├── Icon.tsx       # Material Symbols icon component
        │   └── index.ts       # Barrel export
        ├── scan/
        │   ├── SecurityBanner.tsx
        │   ├── RiskGauge.tsx
        │   ├── RedFlagsList.tsx
        │   ├── RedFlagCard.tsx
        │   ├── ScanActions.tsx
        │   └── index.ts       # Barrel export
        ├── match/
        │   ├── ResumeCard.tsx
        │   ├── MatchScoreCard.tsx
        │   ├── SkillGapList.tsx
        │   ├── KeywordList.tsx
        │   ├── ApplyButton.tsx
        │   ├── MatchFooter.tsx
        │   └── index.ts       # Barrel export
        └── shell/
            ├── TopAppBar.tsx
            ├── SideNav.tsx
            ├── Footer.tsx
            └── index.ts       # Barrel export
```

**Pattern for adding new features:**
1. Add types to `types/index.ts`
2. Add demo data / constants to `data/content.ts`
3. Create component files in `components/<feature>/<ComponentName>.tsx`
4. Create barrel `components/<feature>/index.ts`
5. Compose into a view in `views/<FeatureName>View.tsx`

## Missing / Undefined Conventions

- **No linter** (ESLint, Biome, etc.) — no consistent code style enforcement; could lead to drift.
- **No formatter** (Prettier) — inconsistent whitespace/formatting risk.
- **No `.editorconfig`** — no cross-editor settings baseline.
- **No commit hooks** (Husky, lint-staged) — no pre-commit quality gates.
- **No path aliases** in `tsconfig.json` — all imports are deeply relative, brittle to refactoring.
- **No testing convention** — no test runner, no test files, no test utility patterns (see TESTING.md).
- **No CSS class naming convention** — Tailwind is inline; custom classes use kebab-case but no BEM or systematic methodology.
- **No i18n convention** — all user-facing strings are hardcoded in `data/content.ts` or inline in components.
- **No explicit accessibility conventions** — aria attributes, roles, keyboard navigation patterns are not standardized.
- **No error boundary pattern** — no React error boundaries or error fallback components exist.
- **No performance conventions** — no `React.memo`, `useMemo`, `useCallback` usage pattern defined.
- **Duplicate type definition** — `IconName` exists in two places (`types/index.ts` and `Icon.tsx`) with no single source of truth.

---

*Convention analysis: 2026-07-05*
