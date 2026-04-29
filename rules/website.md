# Website Build Rules

Read this file at the start of any frontend/website build: `Read rules/website.md`

## Pre-Design Phase (MANDATORY — in order before any HTML)

### Step 1 — Brand Extraction
- Check `brand_assets/{client_slug}/` for logo, colors, fonts
- Missing → run `tools/extract_brand.py` (Brandfetch via `BRANDFETCH_API_KEY`)
- Brandfetch fails → use `mcp__21st-magic__logo_search` to find visual logo references

### Step 2 — Design Inspiration
- Call `mcp__21st-magic__21st_magic_component_inspiration` for **hero + 1 reference section only**. Extrapolate to remaining sections.
- Review `inspiration/notes.md` for Awwwards/Godly/Dribbble patterns
- Read `inspiration/components/{section}.html` only for the section currently being built

### Step 3 — Skills
- Invoke `frontend-design` for new builds and major redesigns. Skip for minor tweaks.
- Brand from scratch → also invoke `design`; full token system → also invoke `design-system`

### Step 4 — Image Generation
- `KIE_API_KEY` set → invoke `nano-banana-image-gen` + `tools/scripts/generate_kie.py`. Use Dense Narrative JSON format from `master_prompt_reference.md`. `16:9` hero, `4:5` cards. Save to `output/assets/{slug}/` and `output/prompts/{slug}/`.
- Fallback order: `KIE_API_KEY` → `GEMINI_API_KEY` (`tools/generate_images.py`) → `STABILITY_API_KEY` → `placehold.co`

### Step 5 — Animation Plan
- Decide AOS sections and whether any section warrants OGL 3D.
- Write a 3-line animation plan comment at the top of the file before coding.

---

## Reference Images
- Provided → match layout/spacing/type/color exactly. `placehold.co` for images, generic copy. Do not improve.
- Not provided → design from scratch (see guardrails below).
- **2 screenshot rounds:** Round 1 = layout/structure/color. Round 2 = spacing/type/animation/polish. Round 3 only on regression.

## Local Server & Screenshots
- Always serve on localhost: `node serve.mjs` (port 3000). Never `file:///` URLs. Don't start a second instance.
- Screenshot: `node screenshot.mjs http://localhost:3000` → `./temporary screenshots/screenshot-N.png`
- Label suffix: `node screenshot.mjs http://localhost:3000 label` → `screenshot-N-label.png`
- After screenshot: read PNG with Read tool → analyze → **never re-read a PNG already analyzed this session** (record findings as text)
- Specifics when comparing: "heading is 32px but should be ~24px", "card gap 16px should be 24px"
- Check: spacing/padding, font size/weight/line-height, colors (exact hex), alignment, border-radius, shadows

## Output Defaults
- Single `index.html`, all styles inline. Tailwind CDN. `placehold.co/WIDTHxHEIGHT`. Mobile-first.

## Brand Assets
- Always check `brand_assets/{client_slug}/` before generating. Use real logo/colors if present — never placeholders when real assets exist.

## Anti-Generic Guardrails
- **Colors:** Never default Tailwind (indigo-500, blue-600). Custom brand color derived palette.
- **Shadows:** Layered, color-tinted, low opacity. Never flat `shadow-md`.
- **Typography:** Display/serif + clean sans pair. Tight tracking (`-0.03em`) on headings, `1.7` body line-height. Same font for both = FAIL.
- **Gradients:** Multiple radial layers + SVG noise grain for depth.
- **Animations:** Only `transform`/`opacity`. Never `transition-all`. Spring easing only.
- **Interactive states:** hover + focus-visible + active on every clickable. No exceptions.
- **Images:** Gradient overlay (`bg-gradient-to-t from-black/60`) + color treatment with `mix-blend-multiply`.
- **Sections required:** sticky nav, full-viewport hero, social proof (reviews/logos), services grid, CTA strip, contact, footer.
- **Hero:** video bg / parallax + gradient / SVG grain texture / OGL canvas — never flat solid-color hero.
- **Typography scale:** `clamp()` on ALL headings. H1 min: `clamp(42px, 8vw, 120px)`. Never fixed px on display text.
- **CTAs:** Sub-label or directional icon on every button. Never bare "Submit" / "Contact Us" — use specific action copy.
- **Social proof:** Real reviews if `GOOGLE_PLACES_API_KEY` set (`tools/gather_business_info.py`). Otherwise styled placeholder cards.
- **Logo:** Never text-only. `mcp__21st-magic__logo_search` → inline SVG or styled wordmark.

## Personalization Reasoning (read before any design decision)

Before calling 21st.dev or touching any HTML, check if `.tmp/design_brief.json` exists.

### Client Mode (brief present)
- Read `design_brief.animation_palette` — implement exactly those 3 archetypes, no others
- Use `design_brief.twentyfirst_queries[0]` for hero inspiration query
- Use `design_brief.twentyfirst_queries[1]` for trust/proof section query
- Use `design_brief.twentyfirst_queries[2]` for CTA section query
- Every color and font decision must be justified against `adjectives` + `emotional_target`
- Run `competitor-monitor` skill on `competitor_urls` before touching HTML
- The `differentiation_angle` must be visible in the hero headline — not buried below fold

### Demo Mode (no brief / mode: demo)
- Derive palette from `visual_personality` in `business_info.json`:
  - minimal → `slow_parallax, fade_up_stagger, magnetic_button`
  - bold → `marquee, spring_hover, grid_entrance`
  - warm → `fade_up_stagger, 3d_tilt, stat_counter`
  - corporate → `clip_path_reveal, fade_up_stagger, stat_counter`
  - modern → `cursor_aura, clip_path_reveal, spring_hover`
- Compose 21st.dev query as: `"{industry} {visual_personality} editorial"`

### Never apply all archetypes at once — max 3 per build

---

## Animation Archetypes — Full Library

Pick from this list based on palette. Never invent others.

| Archetype | When to use | Implementation |
|---|---|---|
| **cursor_aura** | Premium/prestige heroes | `mousemove` → CSS `--x`/`--y` custom props → `radial-gradient` on `::before` pseudo-element |
| **marquee** | Tagline strips, keyword rows | CSS `@keyframes marquee` with `translateX(-50%)`, duplicated content for seamless loop; or scroll-driven `animation-timeline: scroll()` |
| **clip_path_reveal** | Section headings on scroll | `IntersectionObserver` → `clip-path: inset(0 100% 0 0)` → `inset(0 0% 0 0)` with `transition: clip-path 0.8s cubic-bezier(0,1,0.5,1)` |
| **grid_entrance** | Service/feature card grids | `IntersectionObserver` + per-card `animation-delay` (0.1s × index), `translateY(40px)` → `0` |
| **magnetic_button** | Primary CTAs | `mousemove` on button bounding rect → `transform: translate(dx*0.3, dy*0.3)`, max 8px, reset on `mouseleave` |
| **slow_parallax** | Background images/layers | `scroll` listener → `transform: translateY(scrollY * 0.25)` on bg element |
| **fade_up_stagger** | Any list or card group | `IntersectionObserver` + staggered `opacity 0→1` + `translateY 24px→0`, 0.08s per item |
| **3d_tilt** | Card grids | `mousemove` → `rotateX`/`rotateY` max 10°, `perspective: 1000px` on parent, specular `<div>` inside |
| **stat_counter** | Numeric stats | RAF lerp from 0 to target on `IntersectionObserver`, never static |
| **spring_hover** | Buttons and links | `cubic-bezier(0.34, 1.56, 0.64, 1)` on `transform: scale(1.03) translateY(-2px)` |

**AOS is always included as baseline** (`unpkg.com/aos@2.3.1`). Palette archetypes are additive on top.

---

## Dead CTA Rule (NON-NEGOTIABLE)

A button or `<a>` is rendered **only if** it has a real destination:
- Section anchor: `href="#services"`, `href="#contact"`, etc.
- External URL or `tel:` / `mailto:`
- `onclick` that opens a modal with actual inline content
- WhatsApp: `href="https://wa.me/..."`

**Forbidden:** `href="#"` on any interactive element that is meant to navigate. `href="#"` is only acceptable on the logo mark (scroll-to-top). Any "Ver más" / "Más información" / "Ver detalles" button without a destination → either wire it to a real anchor/modal, or remove it. No dead CTAs ever.

## AI Slop Test (MANDATORY before any screenshot or delivery)

Ask: "Does this look AI-made?" If yes, redesign.

Fails on:
- Purple-to-blue gradient as primary · cyan neon on dark · glassmorphism on every card
- Every section centered (use asymmetric layouts) · generic icon+heading+2-line card grid (3–6×)
- Bounce/elastic easing · emoji as icons (use inline SVG) · same heading/body font weight
- Inter, Roboto, Arial, Open Sans, or system-ui as heading font
- Hero H1 with generic copy not from real business data

## Content Accuracy (NON-NEGOTIABLE)

**Allowed sources:** `tools/gather_business_info.py` · real Google reviews · `brand_assets/{slug}/` · explicit user content

**Forbidden:** invented years/team sizes/stats/certs/awards · fabricated "500+ clients" / "98% satisfaction" · generic inferred services · fake testimonials with invented names

Missing data → honest placeholder `[Founded Year]` or omit. Never fill with fiction.

## Copy Humanizer — Banned AI Patterns

**Banned words:** "delve" "tapestry" "leverage" "innovative" "seamlessly" "robust" "dynamic" "cutting-edge" "state-of-the-art" "solution" "empower" "transformative" "unlock your potential" "synergy" "holistic" "bespoke" (unless actually custom) "your journey" "we are dedicated to" "our passion" "at the heart of" "in today's fast-paced world"

**Banned structures:** benefit stacking ("Quality. Precision. Trust.") · generic CTAs ("Contact Us Today", "Get Started") · rhetorical questions ("Ready to take your business to the next level?") · overlong hero subheadlines

Replace with specific, concrete language from real business data. Vary sentence rhythm.

## Hard Rules
- No sections/features/content beyond what's in the reference or confirmed data
- Match reference — do not "improve" or add to it
- Do not stop after one screenshot pass
- Do not use `transition-all`
- Do not use default Tailwind blue/indigo as primary color
