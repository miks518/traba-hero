# PROJECT: Trabahero

**A Universal Visual Job-Scam Detection System for Filipino Job Seekers.**

## What This Is
Filipino job seekers are increasingly targeted by sophisticated online scams across social media (Facebook, TikTok) and traditional job boards. Trabahero protects users by providing an extension that captures job post screenshots, sends them to a FastAPI backend for AI-powered scam analysis, and renders a visual verdict with red flags and recommended steps.

**Two codebases in this repo:**
- `entrypoints/` — WXT browser extension (React 19 + TypeScript + Tailwind)
- `backend/` — FastAPI Python backend (OpenRouter AI, modular structure)

## Completed
- [x] **Phase 1**: WXT + Tailwind + Material Symbols foundation
- [x] **Phase 2**: Scam Scan UI (SecurityBanner, RiskGauge, RedFlagsList), element picker overlay, manual crop, multi-image grid (max 4)
- [x] **Phase 3**: Modular FastAPI backend with OpenRouter AI, prefilter, typed schemas, `.env` config
- [x] **INT-01 (partial)**: ScamScanView wired to `POST /api/scan` — real AI verdicts render in UI

## Remaining
- [ ] **INT-02**: Wire ResumeMatchView to real backend API
- [ ] **Cleanup**: `lib/api.ts` still references old `/api/chat` — needs update
- [ ] **Cleanup**: `AiTestView.tsx` calls `/api/chat` which no longer exists

## Context
- **Extension**: WXT v0.20 + React 19 + Tailwind CSS 3.4 (MV3)
- **Backend**: FastAPI + OpenRouter (`openai` SDK at `https://openrouter.ai/api/v1`)
- **Design**: Dark theme, custom tokens in `tailwind.config.js` (Vigilance Yellow/Gold secondary)
- **APIs**: All at `http://localhost:8000`

## Constraints
- Extension `host_permissions` already includes `http://localhost:8000/*`
- `postinstall` runs `wxt prepare` — required before `tsc`
- Backend `.env` must have `OPENROUTER_API_KEY` set

## Out of Scope
- Database storage (verdicts are ephemeral)
- User accounts (single shared auth key)
- Custom model hosting (OpenRouter interim, fine-tuned model later)

*Last updated: 2026-07-07*
