---
name: Sentinel Path
colors:
  surface: '#f8f9fa'
  surface-dim: '#d9dadb'
  surface-bright: '#f8f9fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f5'
  surface-container: '#edeeef'
  surface-container-high: '#e7e8e9'
  surface-container-highest: '#e1e3e4'
  on-surface: '#191c1d'
  on-surface-variant: '#434653'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f2'
  outline: '#737784'
  outline-variant: '#c3c6d5'
  surface-tint: '#1d59c1'
  primary: '#003c90'
  on-primary: '#ffffff'
  primary-container: '#0f52ba'
  on-primary-container: '#bcceff'
  inverse-primary: '#b0c6ff'
  secondary: '#7c5800'
  on-secondary: '#ffffff'
  secondary-container: '#feb700'
  on-secondary-container: '#6b4b00'
  tertiary: '#870001'
  on-tertiary: '#ffffff'
  tertiary-container: '#b20806'
  on-tertiary-container: '#ffbfb5'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d9e2ff'
  primary-fixed-dim: '#b0c6ff'
  on-primary-fixed: '#001945'
  on-primary-fixed-variant: '#00419c'
  secondary-fixed: '#ffdea8'
  secondary-fixed-dim: '#ffba20'
  on-secondary-fixed: '#271900'
  on-secondary-fixed-variant: '#5e4200'
  tertiary-fixed: '#ffdad5'
  tertiary-fixed-dim: '#ffb4a8'
  on-tertiary-fixed: '#410000'
  on-tertiary-fixed-variant: '#930002'
  background: '#f8f9fa'
  on-background: '#191c1d'
  surface-variant: '#e1e3e4'
typography:
  headline-sm:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '700'
    lineHeight: 24px
  headline-xs:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 22px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.03em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  container-padding: 16px
  stack-gap: 12px
  inline-gap: 8px
  section-margin: 20px
  compact-padding: 4px
---

## Brand & Style

The design system is engineered for a high-utility Chrome extension that acts as a vigilant assistant during the job search process. The brand personality is **Professional, Protective, and Efficient**. It aims to evoke a sense of "quiet intelligence"—providing critical security insights and organizational tools without obstructing the user's workflow.

The aesthetic follows a **Corporate / Modern** style with a focus on high-density information display. It prioritizes clarity and utility, utilizing a structured layout that feels like a native extension of the browser's UI. The visual language uses subtle tonal shifts and crisp borders to define hierarchy, ensuring that "Scam Alerts" and "Security Ratings" are immediately distinguishable from standard job data.

## Colors

The palette is anchored in **Sapphire Blue**, a color synonymous with corporate stability and digital security. This is the primary driver for actions and brand presence.

- **Primary (Sapphire Blue):** Used for primary buttons, active states, and brand identifiers. It conveys authority and trust.
- **Secondary (Vigilance Yellow):** Reserved for "Caution" states, such as unverified recruiters or missing job details. It provides a non-aggressive warning.
- **Tertiary (Alert Red):** Used exclusively for high-risk scam detections, malicious links, and critical errors.
- **Neutral (Slate Grays):** A comprehensive range of grays from `#101828` (Text) to `#F9FAFB` (Backgrounds) ensures the UI remains clean and "browser-native."

## Typography

Since the design system must perform within a narrow Chrome Sidebar (typically 320px - 400px), typography is optimized for legibility at small scales. 

**Hanken Grotesk** is used for headlines to provide a sharp, contemporary professional feel. **Inter** is used for all functional body and label text due to its exceptional x-height and clarity in dense data environments. We use a 13px base body size to maximize information density while maintaining accessibility.

## Layout & Spacing

The layout utilizes a **Fixed Sidebar Grid**. Because Chrome extensions are constrained by the browser window's height and a fixed width, the design system focuses on vertical "stacking" logic.

- **The 8px Grid:** All spacing is a multiple of 8px (or 4px for tight components).
- **Safe Margins:** A standard 16px horizontal margin is maintained globally to prevent content from touching the browser edges.
- **Content Blocks:** Information is grouped into cards or "modules" with 12px vertical gaps to create clear visual separation between different job listings or security modules.

## Elevation & Depth

This design system uses **Tonal Layers and Low-Contrast Outlines** rather than heavy shadows to maintain a clean, integrated browser look.

- **Level 0 (Surface):** The main background uses a very light gray (`#F9FAFB`) to differentiate from the web page the user is browsing.
- **Level 1 (Card):** White backgrounds with a 1px solid border (`#E4E7EC`).
- **Level 2 (Active/Hover):** A subtle 4px blur shadow with 5% opacity is used only when a card is hovered or focused to provide tactile feedback.
- **Depth via Color:** Security alerts use subtle background tints (e.g., a very light red wash) rather than elevation to signify importance.

## Shapes

The design system adopts a **Soft (0.25rem)** roundedness profile. This aligns with modern browser UI (like Chrome's address bar and tabs) which has moved toward subtle rounding.

- **Standard Elements:** 4px radius for buttons, inputs, and small chips.
- **Cards/Containers:** 8px radius (`rounded-lg`) for main job cards to provide a distinct but professional container.
- **Status Indicators:** Security "dots" or status pips remain fully circular.

## Components

### Buttons
- **Primary:** Sapphire Blue background, white text. High-contrast, 4px border radius.
- **Outline:** 1px Sapphire Blue border, transparent background. Used for secondary actions like "Save for Later."
- **Ghost:** No border or background unless hovered. Used for "Dismiss" or "Options."

### Security Chips
- **Verified:** Small green pill with a check icon.
- **Risk Level:** Uses the Vigilance Yellow or Alert Red for background tints with dark text of the same hue.

### Input Fields
- Compact height (32px or 36px) with 1px gray borders. Focus state uses a 2px Sapphire Blue "halo" (ring).

### Job Cards
- The core component. Includes a "Security Header" (Rating), "Job Body" (Title/Company), and "Action Footer" (Apply/Save).

### Scam Alerts
- High-visibility banner components that appear at the top of the sidebar. They use the Alert Red background with white bold text and a warning icon to ensure the user's immediate attention.
