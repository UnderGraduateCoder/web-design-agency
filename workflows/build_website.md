# Workflow: Build Business Website

**Output:** `output/index.html` (self-contained) from a plain-language business description.

## Prerequisites
- Python 3.9+, `pip install -r requirements.txt`, `ANTHROPIC_API_KEY` in `.env`

## Expected Outputs
| File | Step | Notes |
|------|------|-------|
| `.tmp/business_info.json` | Step 1 | Structured business data |
| `.tmp/website_copy.json` | Step 2 | Marketing copy (written in passes) |
| `output/hero_preview.html` | Step 2a | Hero-only preview for gate review |
| `output/index.html` | Step 3 | Self-contained HTML |
| `output/assets/logo.png` | Step 1b (opt) | Brand logo |
| `output/assets/hero_background.jpg` | Step 1c (opt) | AI hero image |

---

## Recommended: Multi-Pass Build (use orchestrator)

```bash
# Starter tier (2 passes: hero → full site)
python tools/orchestrate_build.py --tier starter --input "Business description here"

# Pro tier (3 passes: hero → full site → animation polish)
python tools/orchestrate_build.py --tier pro --input "..." --brief .tmp/design_brief.json

# Enterprise tier (4 passes)
python tools/orchestrate_build.py --tier enterprise --input "..." --place-id ChIJ...

# Non-interactive (CI / no gate prompts)
python tools/orchestrate_build.py --tier pro --input "..." --auto
```

The orchestrator runs the full pipeline with gate checkpoints for hero review before committing to the full build. See **Multi-Pass Pipeline** section for the manual step-by-step flow.

---

## Core Pipeline

### Step 0 — Client Brief (Client Mode only — skip for demos)

```bash
# 1. Copy the template and fill it for this client
cp templates/client_brief_template.md .tmp/client_brief.md
# Edit .tmp/client_brief.md — fill all fields, set mode: client

# 2. Build the design brief
python tools/build_brief.py --brief .tmp/client_brief.md
# → Writes .tmp/design_brief.json
```

- Output contains: `animation_palette`, `twentyfirst_queries` (3 targeted strings), `competitor_urls`, `emotional_target`, `differentiation_angle`
- Read `rules/website.md` Personalization Reasoning section before proceeding
- Run `competitor-monitor` skill on the 3 `competitor_urls` from the brief
- Use `twentyfirst_queries[0]` (not a generic "hero section") when calling `mcp__21st-magic__21st_magic_component_inspiration`

For demos: set `mode: demo` or skip Step 0 entirely. Demo builds derive palette from `visual_personality`.

---

### Step 1 — Gather Business Info
```bash
python tools/gather_business_info.py "Business description here"
python tools/gather_business_info.py "Business description" --place-id ChIJ...  # with real Google reviews
```
- Extracts: name, tagline, industry, services, about, colors, contacts, social links
- `--place-id`: pulls real Google rating + top 5 reviews into `business_info.json`
- Edge: short descriptions → LLM infers heavily; review JSON before proceeding
- `GOOGLE_PLACES_API_KEY` missing + `--place-id` → warning, continues without Places data

### Step 2 — Generate Website Copy (Multi-Pass)

#### Step 2a — Pass 1: Hero + SEO
```bash
python tools/generate_copy.py --pass 1
```
- Generates hero headline, CTAs, and SEO metadata only
- Writes partial `.tmp/website_copy.json` (hero + seo keys)
- Establishes the design language for all remaining sections

#### Step 2b — Hero Preview + Gate Review
```bash
python tools/build_website.py --preview
```
- Builds a nav + hero + stub footer page → `output/hero_preview.html`
- **Review this before proceeding.** If unsatisfactory, re-run Step 2a.
- Accepts `--brief` same as full build

#### Step 2c — Pass 2: Remaining Sections
```bash
python tools/generate_copy.py --pass 2
```
- Reads approved hero from `website_copy.json`, locks it
- Generates about, services, social_proof, cta_section, footer, faq, testimonials
- Merges with pass 1 output and overwrites `.tmp/website_copy.json`

> **Legacy single-pass** (still supported for demos/quick runs):
> ```bash
> python tools/generate_copy.py   # no --pass flag = full single pass
> ```

### Step 3 — Build the Website
```bash
python tools/build_website.py                               # Demo mode
python tools/build_website.py --brief .tmp/design_brief.json  # Client mode
```
- Reads both `.tmp/` files → generates `output/index.html`
- Deterministic 1,600-variant system (fonts × layouts × heroes × personalities) keyed on business name
- Auto-adapts to enrichment data: `google_places`, `brand.logo_local_path`, `brand.primary_color`, `hero_image_path`, `hero_video_url`
- With `--brief`: overrides animation palette + color/font decisions from `design_brief.json`

#### Step 3a — Animation Polish Pass (Pro / Enterprise only)
```bash
python tools/build_website.py --polish --tier pro
python tools/build_website.py --polish --tier enterprise
```
- Reads existing `output/index.html` and replaces animation scripts with tier-appropriate palette
- `pro`: spring easing + 3D tilt + slow parallax + stat counters
- `enterprise`: adds cursor aura + clip-path reveals + magnetic buttons
- No structural HTML changes — animation scripts only

---

## Optional Enrichment (run between Step 1 and Step 2)

### Step 1b — Brand Identity (Logo + Colors)
```bash
python tools/extract_brand.py                    # domain auto-inferred from email
python tools/extract_brand.py --domain example.com
```
- Brandfetch API → official logo + hex colors. Falls back to BeautifulSoup scraper.
- Requires `BRANDFETCH_API_KEY` (free tier: 500 req/month)
- Edge: no existing website → scraper fails; site uses Claude-generated colors

### Step 1c — Hero Image (AI-generated)
```bash
python tools/generate_images.py
```
- Gemini (primary, `GEMINI_API_KEY`) → Stability AI fallback (`STABILITY_API_KEY`, ~$0.003/img)
- Valid Stability ratios: `16:9`, `3:2`, `1:1`, `4:5`, `2:3`. **`4:3` is invalid — use `3:2`**
- Saves to `output/assets/<slug>_hero.jpg`, writes `hero_image_path` into `business_info.json`

### Step 1d — Catalog Images (textile/product businesses)
```bash
python tools/generate_catalog_images.py
```
- Generates 4 AI product images (Gemini → Stability fallback). Idempotent (skips existing).

### Step 1e — Hero Video (stock footage)
```bash
python tools/find_hero_video.py
python tools/find_hero_video.py --query "textile fabric weaving"
```
- Requires `PEXELS_API_KEY` (free: 200 req/hour). Saves MP4 + poster, writes into `business_info.json`
- `hero_video_url` takes priority over `hero_image_path` when both present

---

## Full Premium Run
```bash
python tools/gather_business_info.py "Business description" --place-id ChIJ...
python tools/extract_brand.py --domain example.com
python tools/generate_images.py
python tools/generate_copy.py
python tools/build_website.py
```

## API Keys
| Key | Required? | Source |
|-----|-----------|--------|
| `ANTHROPIC_API_KEY` | Yes | console.anthropic.com |
| `GOOGLE_PLACES_API_KEY` | Optional (Step 1) | console.cloud.google.com |
| `BRANDFETCH_API_KEY` | Optional (Step 1b) | brandfetch.com/developers |
| `GEMINI_API_KEY` | Optional (Step 1c) | aistudio.google.com |
| `STABILITY_API_KEY` | Optional (Step 1c fallback) | platform.stability.ai |
| `PEXELS_API_KEY` | Optional (Step 1e) | pexels.com/api |

## Multi-Pass Pipeline (manual step-by-step)

```bash
# Pass 1: hero only
python tools/generate_copy.py --pass 1
python tools/build_website.py --preview      # → output/hero_preview.html (review this)

# Pass 2: full site
python tools/generate_copy.py --pass 2
python tools/build_website.py                # → output/index.html

# Pass 3: animation polish (pro/enterprise only)
python tools/build_website.py --polish --tier pro
```

## Partial Regeneration
```bash
python tools/generate_copy.py && python tools/build_website.py  # legacy: full single-pass copy + HTML
python tools/build_website.py                                    # regenerate HTML only (from existing copy)
python tools/generate_copy.py --pass 1 && python tools/build_website.py --preview  # redo hero only
```

---

## Step 4 — Pre-Launch Security Audit (Auto — Pro/Premium/Enterprise)

`build_website.py` automatically runs a security audit after generating HTML for pro+ tiers:
- Scans for: `eval()`, `innerHTML`, hardcoded secrets, missing CSP, HTTP forms, mixed content
- Saves findings to `output/audits/{client_slug}/findings.json`
- Injects security seal badge into footer
- Logs to `data/clients.db`

Basic tier: no auto-audit. Manual run:
```bash
python tools/security_audit.py --target output/index.html --client-slug <slug> --scan-mode pre_launch --skip-contract
python tools/generate_audit_pdf.py output/audits/<slug>/findings.json <slug>
```

---

## Quality Rules — Learned from Production Errors

**Google Reviews**
- NEVER invent, translate, or complete review text. Render verbatim from Google Places API.
- Empty `review.text` (star-only rating) → render card without quote. Do not fill invented text.
- Keep reviews in their original language. Do not translate.

**WhatsApp vs Landline**
- Only use `wa.me/` links for mobile numbers. Spain: mobile = starts with 6 or 7; landline = starts with 9.
- Using WhatsApp for a landline creates a dead link. `is_spanish_mobile()` in `build_website.py` enforces this.

**Scroll Indicator + AOS**
- `.hero-scroll-indicator` bounce animation class goes on the **inner SVG element only**, not the `<a>` wrapper.
- AOS `data-aos="fade-up"` on parent + bounce on same element → jitter (both use `transform`).
- Use `animation-delay: 1.5s` (after AOS fade completes) + `will-change: transform`.

**Known Constraints**
- Tailwind CDN: fine for single sites; don't use in multi-page production apps
- Contact form is static HTML — integrate Formspree/EmailJS for real submissions
- Gemini model names change frequently; Stability AI fallback is reliable — treat it as de facto primary
- When sending demo to lead, send entire `output/` folder (HTML references `assets/`)
