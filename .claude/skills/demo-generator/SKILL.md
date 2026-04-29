---
name: demo-generator
description: Generate a fully-branded demo website for a specific lead — runs the full build pipeline and outputs to output/demos/{slug}/index.html
argument-hint: "--lead-id 42"
---

# Demo Generator

Takes a `lead_id` from the database, pulls the business's public information, runs the full website builder pipeline (gather_business_info → generate_copy → build_website), and outputs a personalized demo to `output/demos/{business_slug}/index.html`. Updates the lead's status to `demo_sent`.

## When to Invoke

- User says "generate demo", "demo preview", "crear demo para lead", "muéstrale una demo"
- User provides a `lead_id` and asks to show what the business's new site could look like
- After prospecting, user wants to qualify a lead with a personalized demo before outreach
- User says "build a sample site for lead #N"

## Workflow

### Step 1 — Invoke frontend-design skill

**MUST invoke `frontend-design` skill** before writing any HTML — this is a mandatory pre-design step.

### Step 2 — Run the demo generator tool

```bash
python tools/generate_demo_preview.py --lead-id 42
```

The tool:
1. Calls `get_lead(lead_id)` to pull business name, sector, region
2. Runs `gather_business_info.py` with the business description
3. Runs `generate_copy.py` to produce website copy
4. Runs `build_website.py` outputting to `output/demos/{slug}/`
5. Updates lead status to `demo_sent`

### Step 3 — Logo enrichment (MANDATORY)

**MUST call `mcp__21st-magic__logo_search`** with the business name to find visual logo references. Use results to inform the logo treatment in the generated HTML (inline SVG wordmark or icon reference). If the tool returns useful results, open the generated `index.html` and update the logo section.

### Step 4 — Design inspiration (MANDATORY)

**MUST call `mcp__21st-magic__21st_magic_component_inspiration`** for at least the hero and services sections. Use returned patterns to validate that the generated design is on par — or refine the build if it looks generic.

### Step 5 — Screenshot and review

Serve on localhost and screenshot:
```bash
node serve.mjs  # if not already running
node screenshot.mjs http://localhost:3000/output/demos/{slug}/index.html demo-{slug}
```

Read the screenshot. Apply the AI Slop Test. If it fails, refine the design before reporting.

### Step 6 — Report to user

- Confirm: `output/demos/{slug}/index.html` exists
- Share the local URL: `http://localhost:3000/output/demos/{slug}/index.html`
- Lead status is now `demo_sent`
- Suggest next step: run `cold-outreach` to email the demo to the lead

## Edge Cases

- **build_website.py doesn't support --output-dir**: The tool copies `output/index.html` to the demo folder as a fallback. Manual verification required.
- **Lead has no sector**: Use the business name alone for gather_business_info.
- **Lead already at demo_sent or beyond**: Skip status update, just regenerate the demo file.
- **Logo search returns nothing useful**: Use a styled SVG wordmark with the business initials + copper color (#C17A3A).
