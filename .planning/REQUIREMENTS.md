# Requirements: Traba-Hero Frontend

**Defined:** 2026-07-03
**Core Value:** Safety through Simplicity. The user should not need to be tech-savvy to stay safe. One click should be enough to get a safety verdict with a gorgeous, high-fidelity UI that builds trust.

## v1 Requirements

### Environment & Foundation
- [ ] **WXT-01**: Setup WXT workspace with manifest v3 configuration and tailwindcss.
- [ ] **WXT-02**: Load custom fonts (Hanken Grotesk and Inter) and Material Symbols Outlined.

### Sidebar UI Components (Scam Scan)
- [ ] **SCAN-01**: Top App Bar matching Stitch design with gradient Trabahero text and settings buttons.
- [ ] **SCAN-02**: Navigation sidebar to switch between scan and match views.
- [ ] **SCAN-03**: Security Status Banner showing risk level (High Risk Detected).
- [ ] **SCAN-04**: Risk Gauge showing circular SVG gradient score gauge (0-100).
- [ ] **SCAN-05**: Red Flags list rendering details of detected scams with icons.
- [ ] **SCAN-06**: Action button for re-scanning current page with loading spinner animation.

### Sidebar UI Components (Resume Match)
- [ ] **MATCH-01**: Active Resume card showing uploaded PDF file chip.
- [ ] **MATCH-02**: Match Score gauge displaying compatibility percentage and gradient match progress bar.
- [ ] **MATCH-03**: Skill Gaps layout with clickable pill tags.
- [ ] **MATCH-04**: Top Match Keywords checklist.
- [ ] **MATCH-05**: Apply with Match primary 3D button.

### Integration
- [ ] **INT-01**: Connect the Scan UI trigger to the backend API to scan the current webpage and update the Risk Score and Red Flags.
- [ ] **INT-02**: Connect the Resume Match UI to the backend API to retrieve match score and skill gaps.

## v2 Requirements
- **LOCAL-01**: Offline scanning support when backend connection is unavailable.
- **FEED-01**: False positive/negative reporting mechanism with backend logging.

## Out of Scope
| Feature | Reason |
|---------|--------|
| Backend refactoring | Backend is already functional, frontend focuses on layout and integration. |
| User Authentication | Simple local extension state is sufficient for v1. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| WXT-01 | Phase 1 | Pending |
| WXT-02 | Phase 1 | Pending |
| SCAN-01 | Phase 2 | Pending |
| SCAN-02 | Phase 2 | Pending |
| SCAN-03 | Phase 2 | Pending |
| SCAN-04 | Phase 2 | Pending |
| SCAN-05 | Phase 2 | Pending |
| SCAN-06 | Phase 2 | Pending |
| MATCH-01 | Phase 3 | Pending |
| MATCH-02 | Phase 3 | Pending |
| MATCH-03 | Phase 3 | Pending |
| MATCH-04 | Phase 3 | Pending |
| MATCH-05 | Phase 3 | Pending |
| INT-01 | Phase 4 | Pending |
| INT-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-03*
*Last updated: 2026-07-03 after initial definition*
