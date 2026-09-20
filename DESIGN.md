# DESIGN.md — Trabahero Design System

## Brand & Style

The design system is engineered for a high-utility Chrome extension that acts as a vigilant assistant during the job search process. The brand personality is **Professional, Protective, and Efficient**. It evokes a sense of "quiet intelligence"—providing critical security insights without obstructing the user's workflow.

The aesthetic follows a **Corporate / Modern** style with high-density information display. The visual language uses subtle tonal shifts and crisp borders to define hierarchy, ensuring that "Scam Alerts" and "Security Ratings" are immediately distinguishable from standard job data.

**Logo:** Shield + briefcase + magnifying glass SVG icon (`design/trabahero-svg.svg` — archived in repo history).

## Colors

### Light Theme (Sentinel Path — default)

| Token | Hex | Usage |
|---|---|---|
| `primary` | `#003c90` | Primary buttons, active states, brand identifiers |
| `on-primary` | `#ffffff` | Text on primary |
| `primary-container` | `#0f52ba` | Primary container backgrounds |
| `on-primary-container` | `#bcceff` | Text on primary containers |
| `secondary` | `#7c5800` | Caution states, unverified recruiters |
| `secondary-container` | `#feb700` | Secondary container backgrounds |
| `on-secondary-container` | `#6b4b00` | Text on secondary containers |
| `tertiary` | `#870001` | High-risk scam detections, critical errors |
| `tertiary-container` | `#b20806` | Tertiary container backgrounds |
| `on-tertiary-container` | `#ffbfb5` | Text on tertiary containers |
| `error` | `#ba1a1a` | Error states |
| `error-container` | `#ffdad6` | Error container backgrounds |
| `on-error-container` | `#93000a` | Text on error containers |
| `background` | `#f8f9fa` | Main background |
| `on-background` | `#191c1d` | Text on background |
| `surface` | `#f8f9fa` | Surface background |
| `on-surface` | `#191c1d` | Text on surface |
| `surface-dim` | `#d9dadb` | Dimmed surfaces |
| `surface-container-lowest` | `#ffffff` | Lowest container |
| `surface-container-low` | `#f3f4f5` | Low container |
| `surface-container` | `#edeeef` | Default container |
| `surface-container-high` | `#e7e8e9` | High container |
| `surface-container-highest` | `#e1e3e4` | Highest container |
| `surface-variant` | `#e1e3e4` | Surface variant |
| `surface-tint` | `#1d59c1` | Surface tint |
| `on-surface-variant` | `#434653` | Text on surface variants |
| `outline` | `#737784` | Borders, dividers |
| `outline-variant` | `#c3c6d5` | Subtle borders |
| `inverse-surface` | `#2e3132` | Inverted surfaces |
| `inverse-on-surface` | `#f0f1f2` | Text on inverted surfaces |
| `inverse-primary` | `#b0c6ff` | Inverted primary |

### Dark Theme (from UI mockups)

| Token | Hex | Usage |
|---|---|---|
| `background` | `#121317` | Main background |
| `on-background` | `#e3e2e7` | Text on background |
| `surface` | `#121317` | Surface background |
| `on-surface` | `#e3e2e7` | Text on surface |
| `surface-dim` | `#121317` | Dimmed surfaces |
| `surface-container-lowest` | `#0d0e12` | Lowest container |
| `surface-container-low` | `#1a1b1f` | Low container |
| `surface-container` | `#1e1f23` | Default container |
| `surface-container-high` | `#292a2e` | High container |
| `surface-container-highest` | `#343539` | Highest container |
| `surface-variant` | `#343539` | Surface variant |
| `surface-bright` | `#38393d` | Bright surface |
| `on-surface-variant` | `#c7c6ca` | Text on surface variants |
| `outline` | `#909094` | Borders, dividers |
| `outline-variant` | `#46474a` | Subtle borders |
| `primary` | `#c8c6c7` | Primary actions (neutral in dark) |
| `secondary` | `#e9c349` | Gold accent, caution states |
| `secondary-container` | `#af8d11` | Secondary container |
| `on-secondary` | `#3c2f00` | Text on secondary |
| `on-secondary-container` | `#342800` | Text on secondary containers |
| `tertiary` | `#c8c6c7` | Tertiary text |
| `error` | `#ffb4ab` | Error states |
| `error-container` | `#93000a` | Error container |
| `on-error-container` | `#ffdad6` | Text on error containers |

### Metallic Gold Accent (Tactile Buttons)

Used for primary CTA buttons and active nav items:

```css
background: linear-gradient(135deg, #FFDF00 0%, #D4AF37 50%, #B8860B 100%);
border: 1px solid #FFDF00;
box-shadow: 0 4px 0 0 #3c2f00; /* 3D depth */
```

## Typography

| Token | Font | Size | Weight | Line Height | Letter Spacing | Usage |
|---|---|---|---|---|---|---|
| `headline-sm` | Hanken Grotesk | 18px | 700 | 24px | — | Section headings |
| `headline-xs` | Hanken Grotesk | 16px | 600 | 22px | — | Card titles |
| `body-md` | Inter | 14px | 400 | 20px | — | Default body text |
| `body-sm` | Inter | 13px | 400 | 18px | — | Dense body text |
| `label-md` | Inter | 12px | 600 | 16px | 0.02em | Labels, badges |
| `label-sm` | Inter | 11px | 500 | 14px | 0.03em | Small labels, metadata |

**Headline Font:** Hanken Grotesk — sharp, contemporary professional feel.
**Body/Label Font:** Inter — exceptional x-height and clarity in dense data environments.
**Base body size:** 13px to maximize information density in the narrow Chrome sidebar (320–400px).

## Layout & Spacing

The layout utilizes a **Fixed Sidebar Grid** with vertical "stacking" logic.

| Token | Value | Usage |
|---|---|---|
| `container-padding` | 16px | Horizontal margins, prevents touching browser edges |
| `stack-gap` | 12px | Vertical gap between cards/modules |
| `inline-gap` | 8px | Horizontal gap between inline elements |
| `section-margin` | 20px | Gap between major sections |
| `compact-padding` | 4px | Tight inner padding |

- **8px Grid:** All spacing is a multiple of 8px (or 4px for tight components).
- **Content Blocks:** Information grouped into cards with 12px vertical gaps.

## Elevation & Depth

Uses **Tonal Layers and Low-Contrast Outlines** rather than heavy shadows.

| Level | Description | Style |
|---|---|---|
| Level 0 | Main background | Light gray (light) / Dark (#121317) |
| Level 1 | Cards | White/dark bg + 1px solid border |
| Level 2 | Hover/Focus | 4px blur shadow, 5% opacity |
| Depth via Color | Security alerts | Subtle background tints (e.g., light red wash) |

### 3D Tactile Effects

```css
/* Cards */
.tactile-card {
  box-shadow: 0 4px 0 0 rgba(0,0,0,0.4), inset 0 1px 0 0 rgba(255,255,255,0.1);
}
.tactile-card-active {
  box-shadow: 0 0 0 2px #e9c349, 0 4px 0 0 rgba(0,0,0,0.4);
}

/* Buttons */
.tactile-button {
  box-shadow: 0 6px 0 0 #574500, 0 8px 15px rgba(0,0,0,0.3);
}
.tactile-button:active {
  transform: translateY(4px);
  box-shadow: 0 2px 0 0 #574500, 0 4px 10px rgba(0,0,0,0.3);
}
```

## Shapes

| Token | Value | Usage |
|---|---|---|
| `DEFAULT` | 0.25rem (4px) | Buttons, inputs, small chips |
| `lg` | 0.5rem (8px) | Cards, containers |
| `xl` | 0.75rem (12px) | Large cards |
| `full` | 9999px | Pills, status dots |

Soft roundedness aligns with modern Chrome UI. Status indicator dots remain fully circular.

## Components

### Buttons
- **Primary:** Sapphire Blue bg, white text, 4px radius. High-contrast for main actions.
- **Gold CTA:** Metallic gold gradient, 3D shadow depth. Used for "Apply with Match" / "Re-scan".
- **Outline:** 1px Sapphire Blue border, transparent bg. Secondary actions like "Save for Later".
- **Ghost:** No border/bg unless hovered. "Dismiss" or "Options".

### Security Chips
- **Verified:** Small green pill with check icon.
- **Risk Level:** Vigilance Yellow or Alert Red bg tint with dark text of same hue.

### Input Fields
- Compact height (32px or 36px), 1px gray borders.
- Focus state: 2px Sapphire Blue ring.

### Job Cards
- Core component: "Security Header" (Rating) + "Job Body" (Title/Company) + "Action Footer" (Apply/Save).

### Scam Alerts
- High-visibility banner at top of sidebar.
- Alert Red bg, white bold text, warning icon.

### Risk Gauge (Circular)
- SVG circle with gold gradient stroke.
- Score number centered, label below.

### Navigation
- **Side NavBar (80px):** Icon + label, active state uses gold gradient background.
- **Top App Bar:** Sticky, surface-container bg, brand name + action icons.

### Toggle Switch
- Custom styled: 40x24px, gold checked state.

## Icons

Google Material Symbols Outlined, variable font with:
- Weight: 400 (default)
- FILL: 0 (outlined), 1 (filled for active states)
- Gradient: 0
- Optical size: 24

## Custom Scrollbar

```css
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #46474a; border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: #e9c349; }
```

## Tailwind Configuration Reference

Colors are defined as CSS variables in `assets/tailwind.css` using semantic token names. Use `bg-background`, `text-on-surface`, `border-outline`, etc. — never raw hex values in component code.

Dark mode: `darkMode: 'class'` — toggled via `document.documentElement.classList.toggle('dark')`.
