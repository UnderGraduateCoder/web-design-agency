# WAT Website Builder

An open-source framework for generating professional, conversion-optimised business websites using AI. Built on the **WAT architecture** — Workflows, Agents, Tools — which separates probabilistic AI reasoning from deterministic script execution.

## What It Does

Given a plain-language business description, the pipeline produces a fully self-contained `index.html` with:

- Conversion-focused marketing copy (benefit-driven headlines, social proof, clear CTAs)
- 1,600 unique design combinations from a multi-axis variant system (5 font pairings × 4 layouts × 4 hero styles × 4 service layouts × 5 visual personalities)
- Optional Google Places integration for real customer reviews
- Optional AI-generated hero images (Gemini primary / Stability AI fallback)
- Optional stock hero video from Pexels
- Optional real brand identity via Brandfetch API

## Architecture

```
workflows/   # Markdown SOPs — what to do and how
tools/       # Python scripts — deterministic execution
.env         # API keys (never committed)
output/      # Generated websites
```

The agent (Claude) reads workflows, coordinates the tool scripts, recovers from errors, and improves the system over time.

## Quick Start

```bash
pip install -r requirements.txt

# Minimal run (just needs ANTHROPIC_API_KEY in .env)
python tools/gather_business_info.py "Your business description"
python tools/generate_copy.py
python tools/build_website.py
# → output/index.html
```

## Full Premium Pipeline

```bash
# Core + real Google reviews
python tools/gather_business_info.py "description" --place-id ChIJ...

# Brand identity (logo + colours)
python tools/extract_brand.py --domain example.com

# AI hero image
python tools/generate_images.py

# Stock hero video
python tools/find_hero_video.py

# Copy + final HTML
python tools/generate_copy.py
python tools/build_website.py
```

## Local Preview

```bash
node serve.mjs          # serves project root at http://localhost:3000
node screenshot.mjs http://localhost:3000/output/index.html
```

## API Keys

| Key | Purpose | Required? |
|-----|---------|-----------|
| `ANTHROPIC_API_KEY` | Core AI generation | Yes |
| `GOOGLE_PLACES_API_KEY` | Real reviews + rating | Optional |
| `BRANDFETCH_API_KEY` | Brand logo + colours | Optional |
| `GEMINI_API_KEY` | Hero image (primary) | Optional |
| `STABILITY_API_KEY` | Hero image (fallback) | Optional |
| `PEXELS_API_KEY` | Stock hero video | Optional |

Store all keys in `.env` — never committed.

## Sample Output

`output/websites/index.html` — a fictional textile business showcase demonstrating the full design system. No real business data.

## Design System

The generated HTML applies these non-negotiable rules:

- Custom brand colour derived from business context (never default Tailwind palette)
- Layered colour-tinted shadows
- Paired fonts: display serif + clean sans
- Radial gradients + SVG noise texture
- Spring-style easing on `transform` / `opacity` only
- Every interactive element has hover, focus-visible, and active states
- Gradient overlay on all imagery
- Depth layering: base → elevated → floating

## License

MIT
