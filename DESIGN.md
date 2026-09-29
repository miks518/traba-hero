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
| `secondary` | `#4ade80` | Green accent, caution states |
| `secondary-container` | `#af8d11` | Secondary container |
| `on-secondary` | `#3c2f00` | Text on secondary |
| `on-secondary-container` | `#342800` | Text on secondary containers |
| `tertiary` | `#c8c6c7` | Tertiary text |
| `error` | `#ffb4ab` | Error states |
| `error-container` | `#93000a` | Error container |
| `on-error-container` | `#ffdad6` | Text on error containers |

### Accent (Tactile Buttons)

The accent is **green**, not gold. The class names said `gold` for a long time
after the palette moved off gold, which is misleading enough to have caused a
misdiagnosis; they were renamed to `*-accent`. The value is the design system's
`secondary` token, so it resolves per theme.

Used for primary CTA buttons and active nav items, via `.tactile-btn-accent`.
See [Hard shadow](#hard-shadow) for the full rule — the gradient, extrusion, and
highlight all derive from `--tactile-base`, and the button carries a press state
that containers must not.

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

Depth comes from two sources: **tonal layers and a hard shadow**. The shadow is
zero-blur and hard-edged — see [Hard shadow](#hard-shadow) below. It is not a
soft drop shadow and must not be given a blur radius.

| Level | Description | Style |
|---|---|---|
| Level 0 | Main background | Light gray (light) / Dark (#121317) |
| Level 1 | Cards | Surface + 1px solid border + `.tactile-card` |
| Level 2 | Hover/Focus | Accent-tinted background or border |
| Depth via Color | Security alerts | Subtle background tints (e.g., light red wash) |

## Hard shadow

**The technique.** A solid, zero-blur, hard-edged shadow cast straight down
beneath an element, plus a 1px inset highlight along its top edge. The element
reads as a thin slab cut from a material: it has thickness, and the highlight is
where the light lands on it.

Search for it as **"hard shadow"** or **"hard edge shadow"** (Webflow calls a
diagonal, stacked relative the *"long shadow"* — that is a different effect and
**not** this one; NN/g describes it as "flat 2.0 gone wrong — the 3D effects are
purely aesthetic and don't add any meaningful information"). This is also not
**neumorphism**, which is a soft dual-direction shadow and requires the element's
background to match its parent. Neumorphism was evaluated and rejected: it is
too soft for this panel, and on this design system's near-black dark theme
(`--color-background: #121317`) soft shadows have nothing to cast from, so the
panel would read as two different products in its two themes.

**Why it earns its place.** The criticism of flat design was that it stripped
out the signifiers that told a reader what was interactive. NN/g on early UIs:
pseudo-3D shadows and highlights were used "to help users understand the
available actions at a glance." A hard shadow with a press state is a
signifier. Neumorphism is the version that carries no information, which is why
it failed.

### The two tiers — containers and buttons are not the same thing

This is the rule to get right, and the easiest thing to get wrong.

| | **Container** (card, section, list item) | **Button** (anything operable) |
|---|---|---|
| Hard offset shadow | yes | yes, deeper (6px) |
| Inset top highlight | yes | yes, stronger |
| **Presses on activation** | **never** | **yes** |
| `:active` behaviour | none | shadow compresses, element translates down |

A container *looks* three-dimensional and does nothing. A button *looks* the same
way **and moves when you press it**, which is the only cue that tells a reader it
is operable before they touch it.

- **Never** add a press state, `cursor: pointer`, or an `:active` rule to a
  container. It makes a static panel section look like a broken control.
- **Never** make a button static. A hard-shadowed button with no press state
  reads as a label that happens to be shaded, and the affordance is lost.

The compression is the whole point. In `.tactile-btn-accent:active` the shadow
goes `6px → 2px` while the element moves `translateY(4px)` — the slab sinks into
the surface. Shadow alone would only be decoration.

### The CSS, as shipped

```css
/* Container: 3D look, no interaction */
.tactile-card {
  box-shadow: 0 4px 0 0 rgba(0, 0, 0, 0.4),
              inset 0 1px 0 0 rgba(255, 255, 255, 0.08);
  transition: all 0.1s ease;
}

/* Button: 3D look, plus a press. Built from one variable so an accent can
   move the hue without touching the shape. */
.tactile-btn-accent {
  --tactile-base: var(--color-secondary);
  background: linear-gradient(180deg,
      color-mix(in srgb, var(--tactile-base), white 20%) 0%,
      var(--tactile-base) 45%,
      color-mix(in srgb, var(--tactile-base), black 25%) 100%);
  border: 1px solid color-mix(in srgb, var(--tactile-base), white 20%);
  box-shadow: 0 6px 0 0 color-mix(in srgb, var(--tactile-base), black 55%),
              inset 0 1px 0 0 rgba(255, 255, 255, 0.4);
  color: var(--color-on-secondary);
  font-weight: 800;
  transition: all 0.1s ease;
}

/* The press. Both halves are required: the shadow shortens AND the element
   moves. Shadow-only reads as a flicker; move-only reads as a slide. */
.tactile-btn-accent:active {
  transform: translateY(4px);
  box-shadow: 0 2px 0 0 color-mix(in srgb, var(--tactile-base), black 55%);
}

/* A risk accent, applied ALONGSIDE .tactile-btn-accent, never instead of it. */
.tactile-btn-accent.tactile-btn-error {
  --tactile-base: var(--color-error);
}
```

### Recreating it

Three rules, and they are what keep the two tiers honest:

1. **Build the whole treatment from one variable.** Every gradient stop, the
   border, the extrusion, and the highlight derive from `--tactile-base`. An
   accent then moves the hue by moving that one variable, and the geometry is
   identical in both states *by construction* rather than by class bookkeeping.
   A component that adds its own `background` or `box-shadow` has diverged.
2. **Model a colour variant as a compound selector** (`.tactile-btn-accent
   .tactile-btn-error`) so the base class and the variant cannot be swapped for
   one another. Swapping them is exactly how the primary action once flattened
   into a plain button the moment a high-risk result appeared.
3. **Pair every pressable rule with `:active` that moves the element and
   shortens the shadow together.** If you add a button without a press, you have
   built a container.

Use a design token, never a literal colour, for any of it.

## Shapes

| Token | Value | Usage |
|---|---|---|
| `DEFAULT` | 0.25rem (4px) | Buttons, inputs, small chips |
| `lg` | 0.5rem (8px) | Cards, containers |
| `xl` | 0.75rem (12px) | Large cards |
| `full` | 9999px | Pills, status dots |

Soft roundedness aligns with modern Chrome UI. Status indicator dots remain fully circular.

## Components

**Classifying a component: container or button?** Decide this before styling
it, because it decides whether the element gets a press state. See
[Hard shadow](#hard-shadow).

- **Button** — the user can activate it. Gets the hard shadow *and* the
  `:active` press. Buttons, tabs, chips that toggle, nav items.
- **Container** — it holds information. Gets the hard shadow for depth and
  **no** press state. Cards, sections, list rows, panels, the Sources
  disclosure, dialogs.

If you are unsure, ask what happens on click. Nothing happening means container.

### Buttons
- **Primary:** Accent gradient, 4px radius, with a press state. Main actions.
- **Outline:** 1px accent border, transparent bg. Secondary actions.
- **Ghost:** No border/bg unless hovered. "Dismiss" or "Options".
- Every button carries `:active` that shortens its shadow *and* translates it
  down. A button without one is a container and should be built as one.

### Containers
- Section cards and list rows use `.tactile-card`: hard offset shadow, inset
  top highlight, **no** interaction state.
- A container that suddenly needs to be clickable becomes a button — it gains
  the press, not the container's styling.

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
- SVG circle with the accent gradient stroke.
- Score number centered, label below.

### Navigation
- **Side NavBar (80px):** Icon + label; the active state uses the accent gradient background.
- **Top App Bar:** Sticky, surface-container bg, brand name + action icons.

### Toggle Switch
- Custom styled: 40x24px, accent checked state.

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
