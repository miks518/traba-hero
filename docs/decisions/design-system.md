# Decision record — the design system

`DESIGN.md` is the source of truth for tokens, typography, spacing, elevation, shapes and
Tailwind configuration. This record holds the rules that are easy to get wrong.

**Use semantic tokens** (`bg-background`, `text-on-surface`) — **never raw hex values.**

---

## Elevation is a hard shadow, not a soft drop shadow and not neumorphism

A solid zero-blur shadow cast straight down, plus a 1px inset top highlight.

Look it up as "hard shadow" or "hard edge shadow". **Do not call it "long shadow"** (a
diagonal stacked effect from flat-design 2013, which NN/g calls "flat 2.0 gone wrong") or
"**neumorphism**" (soft, dual-direction, needs a background-matched surface — evaluated
and rejected, since on this design system's near-black dark theme soft shadows have nothing
to cast from).

**Never give it a blur radius.**

---

## Containers and buttons are deliberately different

This distinction is the rule most easily lost.

- A **container** (card, section, list row, dialog) gets the 3D look and **no press
  state.**
- A **button** (anything operable) gets the same 3D look **plus** an `:active` press where
  the shadow shortens 6px→2px *and* the element moves `translateY(4px)`.

**That compression is the only cue that tells a reader an element is operable before they
touch it.**

**Never add a press, `cursor: pointer`, or `:active` rule to a container** — a static panel
section that responds to hover reads as a broken control.

**Never build a button without the press** — a hard-shadowed button that does not move
reads as a shaded label.

### The one element that is both

**`.tactile-disclosure`** is the sole case where a tone-filled surface and a press state
meet, and it is worth naming because the rule above says they never do.

The "Full details and sources" header takes the assessment banner's fill so the panel
reads as one object, and it is operable, so it moves. Splitting it therefore meant
**sharing the surface rules with `.tactile-assessment` and adding the press separately** —
a shared selector list for the gradient, border, extrusion and highlight, then a
`:active` rule of its own. Two classes, one surface, no duplicated colour derivation.

It is not `.tactile-assessment` with a class appended, because `.tactile-assessment`
deliberately has no press: the banner reports a measurement, and a banner that sank
under the reader's thumb would read as a control. **The press belongs to the
disclosure and the surface is borrowed; reversing that pairing is the bug to watch
for.**

Its sink is 2px, not the button's 4px. A header sits flush against the body it opens,
and a full-depth press pulls it away from what it just revealed. This replaces
`.tactile-accordion-btn`, which was the same 2px sink on a neutral surface.

---

## The whole button treatment derives from one variable

Every gradient stop, the border, the extrusion, and the highlight come from
`--tactile-base`, **so a risk accent moves the hue by moving that variable and the geometry
is identical in both states by construction.**

A colour variant is a **compound selector** (`.tactile-btn-accent.tactile-btn-error`) so
the base and the variant cannot be swapped for one another — which is exactly how the
primary action once flattened into a plain button the moment a high-risk result appeared.

The classes are named `tactile-btn-accent`, `btn-outline-accent`, and
`text-accent-gradient`. **They said `gold` for a long time after the palette moved off
gold**, which is misleading enough to have caused a misdiagnosis; `secondary` is green
(`#3b6934` light, `#4ade80` dark).

---

## Translucent colour variants must be declared by hand

Tailwind v4 generates `/NN` opacity variants for colours it knows as literals
(`border-amber-500/40`) but **not** for this design system's tokens, which live in a plain
`:root` block.

**A class that is not declared does not fail — it does nothing**, and the element falls
back to Tailwind's preflight `border: 0 solid #e5e7eb`.

Eight of these were silently broken at once (`border-error/40`, `border-tertiary/40`,
`border-outline/45`, `border-secondary/30`, `border-secondary/50`, `border-error/50`, plus
two `hover:` variants); **a red-severity border rendered near-white.**

`borderVariants.test.ts` now fails if a component uses an undeclared custom-token variant.

**Declare new ones in the `@layer components` block of `assets/tailwind.css`, and check the
built CSS** — a declaration that is never used gets tree-shaken away.
