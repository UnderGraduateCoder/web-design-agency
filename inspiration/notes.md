# Design Inspiration Notes
*Sources: godly.website, awwwards.com, dribbble.com — analysed 2026-03-24*
*Note: Full-page screenshots not captured — browser automation agent unavailable. CSS extracted via WebFetch; values are exact where exposed in HTML/stylesheet, estimated where compiled into JS bundles.*

---

## 1. Godly.website

**Personality:** Editorial restraint. The gallery IS the design — there is no hero ego.

**Spacing rhythm:** Dense columnar grid (~8–12px card gap). No wasted whitespace. Every pixel earns its place. Padding is tight and uniform, not generous.

**Type scale:** Minimal — navigation labels only. No large display headline demanding attention. The implicit message: "get out of the way of the work."

**Color contrast:** Dark-mode native. Near-black background (#0d0d0d estimated) + high-contrast off-white text. Strong contrast ratio (estimated >10:1).

**Depth / motion:** Flat at rest. Hover states almost certainly add elevation (scale transform + shadow). The stillness at rest makes hover feel dynamic.

**Key lesson for our builds:**
- Don't fill space for the sake of it. Negative space is active, not absent.
- Hero sections that scream "LOOK AT ME" are generative-template tells. Let the content be the hero.
- Dark-mode native palettes feel premium in 2025. Avoid default white backgrounds.

---

## 2. Awwwards.com

**Personality:** Fluid editorial, award-authority, technical precision.

**Spacing rhythm:** Viewport-relative (`clamp()` throughout). Section vertical padding = `clamp(30px, 6vw, 100px)` — feels generous on desktop, tight on mobile. Inner horizontal = 52px fixed. Gap between nested elements = `clamp(8px, 3vw, 24px)`.

**Type scale:** Aggressive fluid scaling. Heading 1 runs from 42px → 170px across viewport widths. At large sizes, letter-spacing goes tight (likely -0.02em to -0.04em). Line height = 100% on display text — lines almost touch, creating visual mass.

**Color contrast:** Near-black (#222) on white primary, with accent orange (#FA5D29) used *sparingly* only for CTAs and alerts. Feature colors (purple #502bd8, green #aaeec4, blue #49B3FC) appear as badges, never as background fills. Restraint is the rule.

**Depth / layering:**
- Z-index scale: 1 → 5 → 10 → 15 (content → sticky → overlay → modal)
- Shadows: only `0px 0px 6px 0px rgba(0,0,0,0.2)` for dropdowns — almost imperceptible
- Overlays: `rgba(0,0,0,0.3–0.7)` on media — creates depth without heavy drop shadows

**Motion:** Default transition 0.3s ease. Dropdown reveal uses `0.6s cubic-bezier(0, 1, 0.5, 1)` — slight overshoot for spring feel.

**Key lessons for our builds:**
- Use `clamp()` for fluid type and spacing — it's the hallmark of mature CSS.
- Heading at 100% line-height with tight tracking creates visual density that feels designed, not generated.
- Accent color = 1 only. Never two accent colors competing. Everything else is neutral.
- Spring easing (`cubic-bezier(0, 1, 0.5, 1)` or similar) on reveal animations feels alive. `ease` feels dead.
- Semi-transparent overlays beat heavy drop-shadows for depth on imagery.

---

## 3. Dribbble.com

**Personality:** Clean showcase platform, content-forward, light-mode, accessible.

**Spacing rhythm:** 4–6 column responsive grid. Card gap consistent at ~16–24px. Hero has generous vertical padding (~80–120px estimated). Breathing room in the hero contrasts with the density of the grid below — intentional rhythm shift.

**Type scale:** Hierarchical display → subheading → body. Clear weight contrast between levels (likely 700 → 400 → 300 or similar). Body line-height generous (~1.5–1.65).

**Color system:** Neutrals are the backbone — white → f4f4f4 → e4e4e4 → b4b4b4 → 545454 → 242424. The *content* (designer shots) provides the color. The UI steps back. This is the correct approach for a showcase platform.

**Depth:** Cards have minimal shadow at rest (estimated `box-shadow: 0 2px 8px rgba(0,0,0,0.08)`). Hover adds elevation — a clear depth signal without noise at rest.

**Key lessons for our builds:**
- For content-heavy pages: let the imagery carry the color. UI neutrals create a gallery effect.
- Contrast between a generous hero and a denser grid creates rhythm and pacing — the eye gets a breath before diving in.
- Hover elevation on cards (add transform: translateY(-2px) + heavier shadow) is a universally understood "this is interactive" signal.

---

## Cross-Site Synthesis — What Makes These Feel Premium

| Signal | Cheap / Generic | Premium |
|--------|----------------|---------|
| Type scale | Same size everywhere | Dramatic hierarchy, fluid clamp() |
| Letter-spacing | Default | -0.02em to -0.04em on display text |
| Line-height (display) | 1.4–1.6 | 100–110% — lines almost touch |
| Shadows | `box-shadow: 0 4px 6px rgba(0,0,0,0.1)` flat | Layered, color-tinted, near-invisible at rest |
| Accent color | Tailwind indigo-500 | 1 custom accent, used sparingly |
| Spacing | Random Tailwind steps | `clamp()` fluid scale or deliberate token system |
| Transitions | `transition: all 0.3s` | Per-property, spring easing |
| Depth | Everything same z-plane | Base / elevated / floating layering system |
| Dark mode | Forced dark class | Dark-native palette with semantic tokens |
| Imagery | Placeholder or stock | Gradient overlay + color-blend treatment |

---

## 4. Claude-webkit Anti-Slop Principles
*Source: github.com/Hainrixz/claude-webkit — CLAUDE.md*

Patterns that immediately signal a site is AI-generated (avoid all of these):
- AI color palettes: cyan-on-dark, purple-to-blue gradients, neon accents
- Overused fonts: Inter, Roboto, Arial, Open Sans, system-ui on headings
- Centered everything — asymmetric layouts feel designed, not generated
- Generic repeated card grids (icon + heading + 2-line text × 6)
- Bounce/elastic easing on any animation
- Glassmorphism on every surface
- Emoji used as icons

**The AI Slop Test:** before delivery, stand back and ask "does this look AI-made?" If yes, redesign. This is not optional — it is the final quality gate on every build.
