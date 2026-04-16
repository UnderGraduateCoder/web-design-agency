# Agent Instructions

You're working inside the **WAT framework** (Workflows, Agents, Tools). This architecture separates concerns so that probabilistic AI handles reasoning while deterministic code handles execution. That separation is what makes this system reliable.

## The WAT Architecture

**Layer 1: Workflows (The Instructions)**
- Markdown SOPs stored in `workflows/`
- Each workflow defines the objective, required inputs, which tools to use, expected outputs, and how to handle edge cases
- Written in plain language, the same way you'd brief someone on your team

**Layer 2: Agents (The Decision-Maker)**
- This is your role. You're responsible for intelligent coordination.
- Read the relevant workflow, run tools in the correct sequence, handle failures gracefully, and ask clarifying questions when needed
- You connect intent to execution without trying to do everything yourself
- Example: If you need to pull data from a website, don't attempt it directly. Read `workflows/scrape_website.md`, figure out the required inputs, then execute `tools/scrape_single_site.py`

**Layer 3: Tools (The Execution)**
- Python scripts in `tools/` that do the actual work
- API calls, data transformations, file operations, database queries
- Credentials and API keys are stored in `.env`
- These scripts are consistent, testable, and fast

**Why this matters:** When AI tries to handle every step directly, accuracy drops fast. If each step is 90% accurate, you're down to 59% success after just five steps. By offloading execution to deterministic scripts, you stay focused on orchestration and decision-making where you excel.

## How to Operate

**1. Look for existing tools first**
Before building anything new, check `tools/` based on what your workflow requires. Only create new scripts when nothing exists for that task.

**2. Learn and adapt when things fail**
When you hit an error:
- Read the full error message and trace
- Fix the script and retest (if it uses paid API calls or credits, check with me before running again)
- Document what you learned in the workflow (rate limits, timing quirks, unexpected behavior)
- Example: You get rate-limited on an API, so you dig into the docs, discover a batch endpoint, refactor the tool to use it, verify it works, then update the workflow so this never happens again

**3. Keep workflows current**
Workflows should evolve as you learn. When you find better methods, discover constraints, or encounter recurring issues, update the workflow. That said, don't create or overwrite workflows without asking unless I explicitly tell you to. These are your instructions and need to be preserved and refined, not tossed after one use.

## The Self-Improvement Loop

Every failure is a chance to make the system stronger:
1. Identify what broke
2. Fix the tool
3. Verify the fix works
4. Update the workflow with the new approach
5. Move on with a more robust system

This loop is how the framework improves over time.

## File Structure

**What goes where:**
- **Deliverables**: Final outputs go to cloud services (Google Sheets, Slides, etc.) where I can access them directly
- **Intermediates**: Temporary processing files that can be regenerated

**Directory layout:**
```
.tmp/           # Temporary files (scraped data, intermediate exports). Regenerated as needed.
tools/          # Python scripts for deterministic execution
workflows/      # Markdown SOPs defining what to do and how
.env            # API keys and environment variables (NEVER store secrets anywhere else)
credentials.json, token.json  # Google OAuth (gitignored)
```

**Core principle:** Local files are just for processing. Anything I need to see or use lives in cloud services. Everything in `.tmp/` is disposable.

## Bottom Line

You sit between what I want (workflows) and what actually gets done (tools). Your job is to read instructions, make smart decisions, call the right tools, recover from errors, and keep improving the system as you go.

Stay pragmatic. Stay reliable. Keep learning.

## Frontend Website Output Rules

## Pre-Design Phase (MANDATORY — do this before any HTML)

Run all steps below in order. Do not skip any step.

### Step 1 — Brand Extraction
- Check `brand_assets/{client_slug}/` for existing logo, colors, fonts
- If missing: run `tools/extract_brand.py` (uses Brandfetch API via `BRANDFETCH_API_KEY`)
- If Brandfetch returns no result: use `mcp__21st-magic__logo_search` to find visual logo references and inform the logo treatment

### Step 2 — Design Inspiration (MANDATORY for every build)
- Call `mcp__21st-magic__21st_magic_component_inspiration` for EACH major section you plan to build (hero, nav, services, about, CTA, contact, footer) — use returned patterns as the structural and visual baseline
- Review `inspiration/notes.md` for Awwwards/Godly/Dribbble synthesis patterns
- Reference `inspiration/hero.html`, `inspiration/services.html`, `inspiration/cta.html` as structural starting points

### Step 3 — Invoke Skills
- Invoke `frontend-design` skill — ALWAYS, no exceptions
- If building brand identity from scratch: also invoke `design` skill
- If defining a full design token system: also invoke `design-system` skill

### Step 4 — Image Generation
- If `KIE_API_KEY` is set in `.env`: MUST use `nano-banana-image-gen` skill + `tools/scripts/generate_kie.py` to generate hero image. Construct prompt using Dense Narrative JSON format from `master_prompt_reference.md`. Aspect ratio `16:9` for hero, `4:5` for cards. Save image to `output/assets/{client_slug}/` and prompt JSON to `output/prompts/{client_slug}/`.
- Fallback order: `KIE_API_KEY` → `GEMINI_API_KEY` (via `tools/generate_images.py`) → `STABILITY_API_KEY` → `placehold.co`
- Never use `placehold.co` if `KIE_API_KEY` is set.

### Step 5 — Animation Plan
- Decide which AOS scroll animations apply to which sections
- Decide if any section warrants OGL 3D (hero background, product showcase)
- Write a 3-line animation plan in a code comment at the top of the file before coding

---

## Reference Images
- If a reference image is provided: match layout, spacing, typography, and color exactly. Swap in placeholder content (images via `https://placehold.co/`, generic copy). Do not improve or add to the design.
- If no reference image: design from scratch with high craft (see guardrails below).
- Screenshot your output, compare against reference, fix mismatches, re-screenshot. Do at least 3 comparison rounds: Round 1 = layout/structure, Round 2 = spacing/color/type, Round 3 = animation/interaction/polish. Stop only when no visible differences remain or user says so.

## Local Server
- **Always serve on localhost** — never screenshot a `file:///` URL.
- Start the dev server: `node serve.mjs` (serves the project root at `http://localhost:3000`)
- `serve.mjs` lives in the project root. Start it in the background before taking any screenshots.
- If the server is already running, do not start a second instance.

## Screenshot Workflow
- Puppeteer is installed at `C:/Users/adria/AppData/Local/Temp/puppeteer-test/`. Chrome cache is at `C:/Users/adria/.cache/puppeteer/`.
- **Always screenshot from localhost:** `node screenshot.mjs http://localhost:3000`
- Screenshots are saved automatically to `./temporary screenshots/screenshot-N.png` (auto-incremented, never overwritten).
- Optional label suffix: `node screenshot.mjs http://localhost:3000 label` → saves as `screenshot-N-label.png`
- `screenshot.mjs` lives in the project root. Use it as-is.
- After screenshotting, read the PNG from `temporary screenshots/` with the Read tool — Claude can see and analyze the image directly.
- When comparing, be specific: "heading is 32px but reference shows ~24px", "card gap is 16px but should be 24px"
- Check: spacing/padding, font size/weight/line-height, colors (exact hex), alignment, border-radius, shadows, image sizing

## Output Defaults
- Single `index.html` file, all styles inline, unless user says otherwise
- Tailwind CSS via CDN: `<script src="https://cdn.tailwindcss.com"></script>`
- Placeholder images: `https://placehold.co/WIDTHxHEIGHT`
- Mobile-first responsive

## Brand Assets
- `brand_assets/` is a per-client folder. For every client website built, store that client's logo, color guide, and any brand materials in `brand_assets/{client_slug}/` before designing.
- Always check `brand_assets/{client_slug}/` specifically before generating anything for that client. Never use placeholders where real client assets are available.
- If a logo is present, use it. If a color palette is defined, use those exact values — do not invent brand colors.

## Anti-Generic Guardrails
- **Colors:** Never use default Tailwind palette (indigo-500, blue-600, etc.). Pick a custom brand color and derive from it.
- **Shadows:** Never use flat `shadow-md`. Use layered, color-tinted shadows with low opacity.
- **Typography:** Never use the same font for headings and body. Pair a display/serif with a clean sans. Apply tight tracking (`-0.03em`) on large headings, generous line-height (`1.7`) on body.
- **Gradients:** Layer multiple radial gradients. Add grain/texture via SVG noise filter for depth.
- **Animations:** Only animate `transform` and `opacity`. Never `transition-all`. Use spring-style easing.
- **Interactive states:** Every clickable element needs hover, focus-visible, and active states. No exceptions.
- **Images:** Add a gradient overlay (`bg-gradient-to-t from-black/60`) and a color treatment layer with `mix-blend-multiply`.
- **Spacing:** Use intentional, consistent spacing tokens — not random Tailwind steps.
- **Depth:** Surfaces should have a layering system (base → elevated → floating), not all sit at the same z-plane.
- **Sections:** Every website must have at minimum: sticky nav, full-viewport hero, social proof (reviews or logos), services/features grid, CTA strip, contact section, footer. No skeleton sites.
- **Hero:** Must include either a video bg, parallax image with gradient overlay, SVG grain texture, or OGL canvas — never a flat solid-color hero.
- **Typography scale:** Use `clamp()` for ALL heading sizes. H1 minimum: `clamp(42px, 8vw, 120px)`. Never fixed px on display text.
- **Micro-copy:** Every CTA button must have a sub-label or directional icon. Never bare "Submit" or "Contact Us" — use specific action copy like "Get Your Free Quote →".
- **Social proof:** If `GOOGLE_PLACES_API_KEY` is set, pull real reviews via `tools/gather_business_info.py`. Otherwise use styled placeholder review cards with realistic names, ratings, and copy.
- **Hero image:** If `GEMINI_API_KEY` is set, generate a bespoke hero via `tools/generate_images.py`. Fallback: `STABILITY_API_KEY`. Only use placehold.co if both APIs are unavailable.
- **Logo:** Never use text-only placeholder. Use `mcp__21st-magic__logo_search` to find a reference, then implement as inline SVG or a styled wordmark treatment.

## Animation & Interaction (MANDATORY)

These are not optional enhancements — they are minimum quality requirements for every build.

### AOS (Animate on Scroll)
- Include in every build:
  ```html
  <link rel="stylesheet" href="https://unpkg.com/aos@2.3.1/dist/aos.css">
  <script src="https://unpkg.com/aos@2.3.1/dist/aos.js"></script>
  <script>AOS.init({ duration: 800, easing: 'ease-out-cubic', once: true });</script>
  ```
- Apply `data-aos="fade-up"` (or variants: `fade-right`, `zoom-in`, `flip-left`) to every card, heading reveal, stat, and feature block
- Never let content below the fold appear instantly — everything must animate in

### Spring Easing (required on all interactive elements)
- Hover snap: `cubic-bezier(0.34, 1.56, 0.64, 1)`
- Reveal: `cubic-bezier(0, 1, 0.5, 1)`
- Scale on hover: `transform: scale(1.03)` with spring easing on cards and CTAs

### 3D Card Tilt (required on any card grid)
- Mouse-tracking JS: on `mousemove`, compute `rotateX` / `rotateY` from cursor offset within card bounds
- Max tilt: 8–12 degrees. Set `perspective: 1000px` on the card parent.
- Add a specular highlight `<div>` inside each card that repositions with the mouse

### OGL WebGL (use for premium heroes and high-end brands)
- CDN: `https://cdn.jsdelivr.net/npm/ogl@0.0.72/dist/index.umd.js`
- Use for: hero background mesh, particle fields, interactive 3D product views
- Trigger when: user requests 3D, or the client is a tech/luxury/high-end brand

### Stat Counters (required for any numeric stat)
- Any number (years in business, clients served, projects completed) must animate from 0 on scroll using a RAF counter loop
- Never render static numbers for stats

## The AI Slop Test (MANDATORY before finishing any site)

Before any screenshot or delivery, ask: "Does this look like it was made by an AI?" If yes, redesign.

Immediate red flags — if any of these are present, it FAILS:
- Purple-to-blue gradient as primary color scheme
- Cyan-on-dark or neon glow accents
- Glassmorphism on every card (blurred glass is OK once, not everywhere)
- Every section centered — use asymmetric, intentional layouts
- Generic card grids: icon + heading + 2-line text, repeated 3–6 times
- Bounce/elastic easing on any animation
- Emoji used as icons (use inline SVG or Lucide-style SVGs only)
- Same font weight used for heading and body (must visually differentiate)
- Inter, Roboto, Arial, Open Sans, or system-ui as primary heading font
- Hero H1 that says "Your Business, Elevated" or any generic tagline not sourced from the actual business

## Content Accuracy (NON-NEGOTIABLE)

Never invent information. Every piece of content must come from a verified source:

**Allowed sources:**
- Data returned by `tools/gather_business_info.py`
- Real reviews pulled via Google Places API
- Brand assets from `brand_assets/{client_slug}/` or Brandfetch
- Explicit content provided by the user in their message

**Forbidden — will be removed before delivery:**
- Invented founding years, team sizes, employee counts
- Made-up certifications, awards, or accreditations
- Fabricated stats: "500+ clients", "20 years of experience", "98% satisfaction rate"
- Generic services inferred from industry when real services aren't confirmed
- Fake testimonials with invented names and quotes — use clearly-marked placeholder format, or real Google Places reviews only
- Generic benefit copy like "We are passionate about quality" — use only specifics from the data

**When a data point is missing:** use an honest placeholder like `[Founded Year]` or omit the stat entirely. Do NOT fill with plausible-sounding fiction.

## Copy Humanizer — Banned AI Writing Patterns

Before finalizing any website copy, scan every sentence. Remove all of the following:

**Banned words:** "delve," "tapestry," "leverage," "innovative," "seamlessly," "robust," "dynamic," "cutting-edge," "state-of-the-art," "solution," "empower," "transformative," "unlock your potential," "synergy," "holistic," "bespoke" (unless genuinely custom), "your journey," "we are dedicated to," "our passion," "at the heart of," "in today's fast-paced world"

**Banned structures:**
- Benefit stacking: "Quality. Precision. Trust." (3 vague nouns on separate lines)
- Generic CTAs: "Contact Us Today", "Get Started", "Learn More" — use action-specific copy tied to the real business
- Rhetorical questions: "Ready to take your business to the next level?"
- Overlong mission statements in the hero subheadline

Replace with specific, concrete, direct language from the real business data. Vary sentence rhythm — short punchy sentences mixed with longer ones.

## Hard Rules
- Do not add sections, features, or content not in the reference
- Do not "improve" a reference design — match it
- Do not stop after one screenshot pass
- Do not use `transition-all`
- Do not use default Tailwind blue/indigo as primary color

---

## Skill Activation Rules

These are hard requirements. When the trigger condition is met, MUST invoke the skill using the `Skill` tool BEFORE proceeding with that work. No exceptions.

---

### 21st.dev Magic (MCP Tools)

These tools are always available via the connected `21st-magic` MCP server. They are NOT skills invoked with the Skill tool — call them directly as MCP tool calls.

**`mcp__21st-magic__21st_magic_component_inspiration`**
- **MUST call** for every major section (hero, nav, services, CTA, contact, footer) before writing that section's HTML — use returned patterns as the structural and visual baseline

**`mcp__21st-magic__21st_magic_component_builder`**
- **MUST call** when building any interactive component (cards, modals, accordions, carousels, tabs, forms) — use the output as the implementation starting point, then customise to brand

**`mcp__21st-magic__21st_magic_component_refiner`**
- **MUST call** after the first screenshot pass on any component that looks generic, flat, or unpolished — feed it the current HTML and request a refinement direction

**`mcp__21st-magic__logo_search`**
- **MUST call** whenever a client logo is not present in `brand_assets/` — use results to inform the logo display treatment (SVG inline, wordmark, icon + text)

---

### UI & Design Skills

**`frontend-design`** (also invocable as `ui-ux-pro-max`)
- **MUST invoke** at the start of every session in which any frontend HTML/CSS/UI code will be written — no exceptions, even for minor edits.

**`design`**
- **MUST invoke** when asked to create or update brand identity, generate a logo, produce corporate identity deliverables, create icons, design social media photos, or establish design tokens for a project from scratch.

**`design-system`**
- **MUST invoke** when creating or updating a design token architecture (three-layer tokens), building component specification docs, generating a Tailwind theme config, defining spacing/typography scales, or producing design-to-code handoff materials.

**`ui-styling`**
- **MUST invoke** when implementing shadcn/ui components, building a React-based UI with Radix primitives, applying utility-first Tailwind styling to a component library, implementing dark mode, or generating canvas-based visual design posters.

**`brand`**
- **MUST invoke** when defining or auditing a client's brand voice, creating messaging frameworks, establishing visual identity guidelines, or reviewing brand consistency across assets.

**`banner-design`**
- **MUST invoke** when creating social media covers, ad banners, website hero images, event banners, print materials, or any standalone creative asset. Covers all 22 art direction styles.

**`slides`**
- **MUST invoke** when creating any HTML presentation, pitch deck, marketing slide deck, or data-driven strategic presentation.

**`video-to-website`**
- **MUST invoke** when user provides a video file and asks for a website, scroll animation, or product showcase — use for structural layout, animation choreography, and frame-extraction workflow reference.

**`nano-banana-image-gen`**
- **MUST invoke** for every hero image generation. Use `tools/scripts/generate_kie.py` pipeline via `KIE_API_KEY`. Save all images to `output/assets/{client_slug}/` and all prompts to `output/prompts/{client_slug}/`. Always use the Dense Narrative JSON format from `master_prompt_reference.md`. Never use placehold.co if `KIE_API_KEY` is set.

---

### Browser Automation

**`browser`**
- **MUST invoke** when automating a real browser session — navigating to URLs, clicking elements, filling forms, scraping page content, or taking browser screenshots via the automation API (distinct from the Puppeteer localhost screenshot workflow).

---

### Development Workflow

**`pair-programming`**
- **MUST invoke** when the user explicitly requests a structured pair programming session (driver/navigator mode), TDD red-green-refactor cycles, a live debugging session with role switching, or a guided learning/refactor walkthrough.

---

### GitHub Skills

**`github-code-review`**
- **MUST invoke** when reviewing a pull request, performing automated code analysis on a diff, enforcing quality gates, or running security/performance analysis on submitted code.

**`github-workflow-automation`**
- **MUST invoke** when creating or modifying GitHub Actions workflows, setting up CI/CD pipelines, automating repository operations, or configuring security scanning in a pipeline.

**`github-release-management`**
- **MUST invoke** when planning a software release, generating changelogs, bumping semantic versions, coordinating multi-platform builds, or managing hotfix rollbacks.

**`github-project-management`**
- **MUST invoke** when managing GitHub Issues, automating project board state, running sprint planning, tracking milestone progress, or coordinating team workflows across a repo.

**`github-multi-repo`**
- **MUST invoke** when synchronizing packages or versions across multiple repositories, managing cross-repo dependencies, standardizing architecture templates, or performing org-wide repository operations.

---

### AgentDB Skills

**`agentdb-vector-search`**
- **MUST invoke** when implementing semantic search, document similarity retrieval, or vector-based intelligent lookup using AgentDB.

**`agentdb-memory-patterns`**
- **MUST invoke** when implementing persistent agent memory (session memory, episodic memory, or semantic long-term memory) backed by AgentDB.

**`agentdb-optimization`**
- **MUST invoke** when optimizing AgentDB storage or query performance — applying quantization (4–32x memory reduction), tuning HNSW indexing, or profiling retrieval latency.

**`agentdb-learning`**
- **MUST invoke** when creating or training AI learning plugins using any of AgentDB's 9 reinforcement learning algorithms.

**`agentdb-advanced`**
- **MUST invoke** when configuring QUIC-based AgentDB synchronization, managing multi-database setups, or implementing advanced AgentDB features beyond standard CRUD and search.

---

### Intelligence & Learning

**`reasoningbank-agentdb`**
- **MUST invoke** when implementing a ReasoningBank system backed by AgentDB's HNSW vector DB (150x faster search), including trajectory tracking, verdict judgment, or experience replay.

**`reasoningbank-intelligence`**
- **MUST invoke** when building adaptive learning pipelines, pattern recognition systems, or strategy optimization loops that learn from agent outcomes over time.

---

### Swarm & Orchestration

**`swarm-orchestration`**
- **MUST invoke** when coordinating parallel agent swarms via agentic-flow for any multi-agent task requiring dynamic task assignment, load balancing, or inter-agent communication.

**`swarm-advanced`**
- **MUST invoke** when running complex multi-agent research, development, or testing workflows that require hierarchical swarm patterns, consensus protocols, or adaptive topology switching.

---

### SPARC & Methodology

**`sparc-methodology`**
- **MUST invoke** when executing a full SPARC development cycle (Specification → Pseudocode → Architecture → Refinement → Completion) on any non-trivial software feature or system.

**`stream-chain`**
- **MUST invoke** when building stream-JSON multi-agent pipelines, chaining sequential agent outputs as inputs to downstream agents, or constructing data transformation workflows.

---

### claude-flow v3 Development

These skills apply exclusively when working on the claude-flow v3 codebase internals. Do not invoke for general website building work.

**`v3-core-implementation`**
- **MUST invoke** when implementing new DDD domain modules, clean architecture layers, or dependency injection patterns within claude-flow v3.

**`v3-ddd-architecture`**
- **MUST invoke** when performing bounded context identification, aggregate design, or enforcing ubiquitous language in the claude-flow v3 domain model.

**`v3-integration-deep`**
- **MUST invoke** when implementing ADR-001 (eliminating 10,000+ lines of duplicate code via deep agentic-flow@alpha integration).

**`v3-mcp-optimization`**
- **MUST invoke** when optimizing the MCP server transport layer, reducing latency, or improving throughput in claude-flow v3's MCP interface.

**`v3-memory-unification`**
- **MUST invoke** when merging multiple memory subsystems into the unified AgentDB HNSW backend targeting 150x–12,500x search improvement.

**`v3-performance-optimization`**
- **MUST invoke** when targeting v3 performance benchmarks: Flash Attention 2.49x–7.47x speedup, token usage reduction of 50–75%, or WASM SIMD acceleration.

**`v3-security-overhaul`**
- **MUST invoke** when addressing security CVEs, implementing zero-trust design, or conducting a security architecture review within claude-flow v3.

**`v3-swarm-coordination`**
- **MUST invoke** when orchestrating the 15-agent hierarchical mesh coordination pattern for v3 parallel implementation work.

**`v3-cli-modernization`**
- **MUST invoke** when modernizing CLI commands, interactive prompts, or the hooks system architecture in claude-flow v3.

---

### Meta & Tooling

**`hooks-automation`**
- **MUST invoke** when configuring new Claude Code hooks in `settings.json`, debugging existing hook behavior, or designing automated coordination patterns triggered by tool events.

**`skill-builder`**
- **MUST invoke** when creating a new Claude Code skill file — to ensure correct YAML frontmatter, progressive disclosure structure, and trigger condition formatting.

**`verification-quality`**
- **MUST invoke** when implementing truth scoring systems, code quality verification pipelines, or automatic rollback mechanisms for agent-generated outputs.

---

## Security Audit Service

### Hard Rules — No Exceptions

- **NEVER** scan or probe any client system without a signed `authorization_contract_template.md` on file from the client
- Always save the signed contract to `brand_assets/{client_slug}/authorization_signed.pdf` **before** running `tools/security_audit.py` — the tool will abort if it is missing
- All client-facing reports must be written entirely in **Spanish**
- All findings must include: severity (Alta/Media/Baja), affected files and line numbers, and specific remediation guidance
- Follow Anthropic's coordinated disclosure practice — never publish, share, or disclose findings outside the client engagement without written consent
- The `/security-review` slash command is for interactive use inside Claude Code (self-audits, exploration); `tools/security_audit.py` is for programmatic client engagements
- Never run `tools/security_audit.py` without a signed contract — use `--skip-contract` only for auditing this project itself

### Workflow Reference

1. Read `workflows/security_audit.md` for the full SOP before starting any engagement
2. Fill `templates/authorization_contract_template.md` → have client sign → save PDF to `brand_assets/{client_slug}/authorization_signed.pdf`
3. Run: `python tools/security_audit.py --target <url_or_path> --client-slug <slug>`
4. Render findings into `templates/audit_report_template.md` → deliver in Spanish to client

### Tool Locations

| File | Purpose |
|---|---|
| `tools/security_audit.py` | Programmatic audit runner (requires signed contract) |
| `workflows/security_audit.md` | Full engagement SOP |
| `templates/audit_report_template.md` | Client-facing report template (Spanish) |
| `templates/authorization_contract_template.md` | Authorization form (Spanish, must be signed before scan) |
| `security-review/` | Anthropic's official framework (cloned — do not modify) |
| `.claude/commands/security-review.md` | Interactive `/security-review` slash command |
