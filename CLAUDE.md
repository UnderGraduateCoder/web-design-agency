# Agent Instructions — WAT Framework (Workflows · Agents · Tools)

You coordinate between workflow SOPs (`workflows/`) and deterministic execution scripts (`tools/`). Read the workflow, call the right tool, recover from errors, improve the system.

## Operating Rules

1. **Check `tools/` first** before writing any new script.
2. **On error:** read the full trace → fix → retest (ask before re-running paid API calls) → document the fix in the workflow.
3. **Don't overwrite workflows** without asking — they're instructions, not scratch space.
4. **Self-improvement loop:** identify → fix → verify → update workflow → move on.

## File Structure

```
tools/       # Deterministic execution scripts
workflows/   # Markdown SOPs (your instructions)
.tmp/        # Regeneratable intermediates — disposable
.env         # API keys (NEVER anywhere else)
```

Deliverables go to cloud services (Google Sheets, Slides, etc.) — local files are for processing only.

## Domain Rules (read before starting domain work)

| Domain | Action |
|---|---|
| **Frontend / website** | `Read rules/website.md` before any HTML/CSS/design task |
| **Security audit** | `Read rules/security.md` before any audit engagement |
| **Business development** | `Read rules/biz-dev.md` before lead/client/outreach work |

---

## Skill Activation Rules

Invoke the listed skill with the `Skill` tool **before** proceeding when the trigger is met. No exceptions.

### Always-On

| Skill | Invoke when |
|---|---|
| `human-writing` | Formal content: blog posts, cold outreach, proposals, audit reports, quotes. **Not for website copy** — `rules/website.md` Copy Humanizer covers it. |
| `fact-check` | Before delivering audit findings, stats, or factual claims in reports, proposals, or outreach with data points |
| `llm-council` | User says "council this", "pressure-test this", "debate this"; genuine strategic decision with real stakes. Not for routine tasks. |

### Design & Frontend

| Skill | Invoke when |
|---|---|
| `frontend-design` | New website builds or major redesigns. Skip for minor HTML/CSS tweaks. |
| `design` | Creating/updating brand identity, logo, corporate identity, icons, or design tokens from scratch |
| `design-system` | Design token architecture, Tailwind theme config, spacing/typography scales, component spec docs |
| `ui-styling` | shadcn/ui, Radix primitives, Tailwind component library, dark mode, canvas visual posters |
| `brand` | Defining/auditing brand voice, messaging frameworks, or visual identity guidelines |
| `banner-design` | Social covers, ad banners, hero images, event banners, print materials, standalone creative assets |
| `slides` | HTML presentations, pitch decks, marketing slides, data-driven strategic presentations |
| `video-to-website` | User provides a video + asks for website, scroll animation, or product showcase |
| `nano-banana-image-gen` | Every hero image generation when `KIE_API_KEY` is set — use `tools/scripts/generate_kie.py` |

### 21st.dev MCP (call directly — NOT via Skill tool)

| Tool | When |
|---|---|
| `mcp__21st-magic__21st_magic_component_inspiration` | Hero + 1 reference section only; extrapolate to remaining sections |
| `mcp__21st-magic__21st_magic_component_builder` | Any interactive component: cards, modals, accordions, carousels, tabs, forms |
| `mcp__21st-magic__21st_magic_component_refiner` | After first screenshot pass if a component looks generic or flat |
| `mcp__21st-magic__logo_search` | No logo in `brand_assets/` |

### Business Dev & Client Ops

| Skill | Invoke when |
|---|---|
| `lead-prospecting` | "buscar clientes", "prospect leads", region + sector combination, finding new leads |
| `demo-generator` | "genera demo", "demo para lead", personalized demo site for a specific lead |
| `cold-outreach` | "contactar lead", "cold email", "enviar email a lead", first contact with prospect |
| `commercial-proposal` | "propuesta comercial", "generate proposal", creating a formal offer PDF |
| `client-onboarding` | "onboard client", "cliente ganado", "won lead", "cerrar cliente", "send the contract" |
| `change-request-quote` | Client wants change outside current plan, "el cliente quiere", "añadir", quote requests — check tier first |
| `blog-writer` | "generar artículo", "blog post", "blog mensual", blog_mensual service |
| `whatsapp-integration` | "añadir WhatsApp", "integrar WhatsApp", whatsapp_widget service |
| `social-content` | "contenido social", "pack de redes", "Instagram", "LinkedIn", social_content_pack |
| `competitor-monitor` | "monitorear competencia", "informe competitivo" — pro/premium/enterprise tier only |
| `ab-testing` | A/B test setup/analysis — **enterprise tier only**, verify `tier == "enterprise"` first; reject otherwise |

### Dev Workflow & GitHub

| Skill | Invoke when |
|---|---|
| `browser` | Automating real browser: navigate URLs, click, fill forms, scrape, browser screenshots |
| `pair-programming` | User requests driver/navigator mode, TDD cycles, live debug, guided refactor |
| `github-code-review` | Reviewing PRs, code analysis on diffs, quality gates, security/perf analysis |
| `github-workflow-automation` | Creating/modifying GitHub Actions, CI/CD pipelines, repo automation |
| `github-release-management` | Releases, changelogs, semantic versioning, multi-platform builds, rollbacks |
| `github-project-management` | GitHub Issues, project boards, sprint planning, milestone tracking |
| `github-multi-repo` | Cross-repo sync, multi-repo dependencies, org-wide operations |

### AgentDB, Intelligence & Swarms

| Skill | Invoke when |
|---|---|
| `agentdb-vector-search` | Semantic search, document similarity, vector-based lookup with AgentDB |
| `agentdb-memory-patterns` | Persistent agent memory (session/episodic/semantic) backed by AgentDB |
| `agentdb-optimization` | AgentDB storage/query optimization, quantization, HNSW tuning |
| `agentdb-learning` | Creating/training AI learning plugins with AgentDB's RL algorithms |
| `agentdb-advanced` | QUIC-based AgentDB sync, multi-database setups, advanced AgentDB features |
| `reasoningbank-agentdb` | ReasoningBank + AgentDB HNSW: trajectory tracking, verdict judgment, experience replay |
| `reasoningbank-intelligence` | Adaptive learning pipelines, pattern recognition, strategy optimization loops |
| `swarm-orchestration` | Parallel agent swarms: task assignment, load balancing, inter-agent comms |
| `swarm-advanced` | Multi-agent workflows with hierarchical patterns, consensus, adaptive topology |
| `sparc-methodology` | Full SPARC cycle on any non-trivial software feature or system |
| `stream-chain` | Stream-JSON multi-agent pipelines, chaining sequential agent outputs |

### Meta & Tooling

| Skill | Invoke when |
|---|---|
| `hooks-automation` | Configuring Claude Code hooks in settings.json, debugging hooks, designing hook patterns |
| `skill-builder` | Creating a new Claude Code skill file |
| `verification-quality` | Truth scoring systems, code quality verification pipelines, automatic rollback mechanisms |

### claude-flow v3 (internal only — not for website/biz-dev work)

| Skill | Invoke when |
|---|---|
| `v3-core-implementation` | New DDD domain modules, clean architecture, dependency injection in claude-flow v3 |
| `v3-ddd-architecture` | Bounded context identification, aggregate design, ubiquitous language enforcement |
| `v3-integration-deep` | ADR-001 — eliminating duplicate code via agentic-flow@alpha integration |
| `v3-mcp-optimization` | MCP server transport layer optimization, latency/throughput in claude-flow v3 |
| `v3-memory-unification` | Merging memory subsystems into unified AgentDB HNSW backend |
| `v3-performance-optimization` | Flash Attention speedup, 50-75% token reduction, WASM SIMD acceleration |
| `v3-security-overhaul` | Security CVEs, zero-trust design, security architecture review in claude-flow v3 |
| `v3-swarm-coordination` | 15-agent hierarchical mesh coordination pattern for v3 parallel work |
| `v3-cli-modernization` | CLI commands, interactive prompts, hooks system architecture in claude-flow v3 |
