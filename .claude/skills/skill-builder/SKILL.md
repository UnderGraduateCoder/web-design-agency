---
name: skill-builder
description: Use when creating new skills, optimizing existing skills, or auditing skill quality. Guides skill development following Claude Code official best practices.
---

## What This Skill Does

Guides the creation and optimization of Claude Code skills using official best practices. Use this whenever:

- Building a new skill from scratch
- Optimizing or auditing an existing skill
- Deciding on advanced features (subagent execution, hooks, dynamic context, etc.)
- Troubleshooting a skill that isn't working correctly

For the complete technical reference on all frontmatter fields, advanced patterns, and troubleshooting, see [reference.md](reference.md).

## Quick Start: What Is a Skill?

A skill is a reusable set of instructions that tells Claude Code how to handle a specific task. Skills live in .claude/skills/[skill-name]/SKILL.md inside your project. When you type /skill-name or describe what you need in natural language, Claude loads the skill's instructions and follows them.

Think of skills as SOPs for Claude. Instead of re-explaining a workflow every conversation, you write it once and invoke it forever.

**How they work under the hood:**

- Your project's CLAUDE.md instructions are always loaded, every conversation
- Skill *descriptions* (from frontmatter) are always loaded so Claude knows what's available
- The full skill content only loads when the skill is actually invoked
- Once loaded, Claude follows the skill's instructions while still respecting your CLAUDE.md rules

---

## Mode 1: Build a New Skill

When building a new skill, run the **Discovery Interview** first. Do NOT start writing files until discovery is complete.

### Discovery Interview

Ask questions using AskUserQuestion, one round at a time. Each round covers one topic. Move to the next round only after the user answers. Keep going until you're 95% confident you understand the skill well enough to build it without further clarification.

**Round 1: Goal & Name** *Why this matters: A clear goal prevents scope creep. The name becomes the /slash-command, so it needs to be memorable and specific.*

- What does this skill do? What problem does it solve or what workflow does it automate?
- What should we call it? (Suggest a name based on their answer -- lowercase, hyphens, max 64 chars)

**Round 2: Trigger** *Why this matters: The description field is how Claude decides whether to load your skill. Bad trigger words mean Claude never uses it. Too broad means Claude fires it when you don't want it.*

- What would someone say to trigger this? (Get 2-3 natural language phrases)
- Should it be user-only (/slash-command), Claude-auto-invocable, or both?
- Does it accept arguments? If so, what? (e.g., a topic, a URL, a file path)

**Round 3: Step-by-Step Process** *Why this matters: Claude follows instructions literally. Vague steps produce vague results. Specific steps produce consistent output every time.*

- Walk me through exactly what should happen from trigger to output. What's step 1? Step 2? Keep going.
- For each step: Does Claude do it directly, or delegate to a subagent/script?
- Does this need to be conversational (back-and-forth with the user) or is it a fire-and-forget task?

**Round 4: Inputs, Outputs & Dependencies** *Why this matters: Skills that don't specify where to find inputs or where to put outputs produce inconsistent results. Nailing this down makes the skill reliable.*

- What inputs does the skill need? (Files, API responses, user arguments, live data)
- What does it produce? (Files, text output, structured data) Where do outputs go?
- Does it need external APIs, scripts, or tools? Which ones?
- Does it need reference files, style guides, templates, or examples?

**Round 5: Guardrails & Edge Cases** *Why this matters: Skills without guardrails can produce unexpected behavior -- wrong outputs, unnecessary API costs, or actions you didn't intend.*

- What could go wrong? What are the common failure modes?
- What should this skill NOT do? Any hard boundaries?
- Are there cost concerns? (API calls, AI image generation, etc.)
- Any ordering or dependency constraints? (e.g., "must check X before doing Y")

**Round 6: Confirmation** *Why this matters: Misunderstandings caught here save you from rebuilding the skill later.*

After all rounds, summarize your understanding back to the user in this format:

## Skill Summary: [name]

**Goal:** [one sentence]

**Trigger:** `/name` + [natural language phrases]

**Arguments:** [what it accepts, or "none"]

**Process:**
1. [step]
2. [step]

**Inputs:** [what it reads/needs]

**Outputs:** [what it produces + where]

**Dependencies:** [APIs, scripts, agents, reference files]

**Guardrails:** [what can go wrong, what to avoid]

Ask: "Does this capture it? Anything to add or change?" Only proceed to building once the user confirms.

**Skipping rounds:** If the user provides enough context upfront (e.g., they describe the full workflow in their first message), skip rounds that are already answered. Don't re-ask what you already know.

### Build Phase

Once discovery is complete, build the skill following these steps:

**Step 1: Choose the skill type**

- **Task skills** (most common) give step-by-step instructions for a specific action. Invoked with /name or natural language.
- **Reference skills** add knowledge Claude applies to current work without performing an action.

**Step 2: Configure frontmatter**

Set these fields based on what you learned in discovery:

- name -- Matches the directory name. Lowercase, hyphens, max 64 chars.
- description -- Written as: "Use when someone asks to [action], [action], or [action]." Include natural keywords from the trigger phrases.
- disable-model-invocation: true -- Set if the skill has side effects (file generation, API calls, costs money).
- argument-hint -- Set if the skill accepts arguments. Shows in the / menu autocomplete.
- context: fork + agent -- Set if the skill is self-contained and doesn't need conversation history.
- model -- Set if a specific model capability is needed.
- allowed-tools -- Set if the skill should have restricted tool access.

Only set fields you actually need. For the full field reference and invocation control matrix, see [reference.md](reference.md).

**Step 3: Write the skill content**

Structure task skills as:

1. **Context** -- Files to read, APIs to call, reference material to load
2. **Step-by-step workflow** -- Numbered steps. Each step tells Claude exactly what to do.
3. **Output format** -- What the result looks like. Include templates, file paths, structured formats.
4. **Notes** -- Edge cases, constraints, what to delegate, what NOT to do.

Content rules:

- Keep SKILL.md under 500 lines. Move detailed reference material to supporting files.
- Use $ARGUMENTS / $N for dynamic input from arguments.
- Be specific about agent delegation -- include exact prompt text.
- Specify all file paths (inputs, outputs, scripts, references).

**Step 4: Add supporting files (if needed)**

Add them alongside SKILL.md in the same directory. Reference them from SKILL.md so Claude knows they exist. Supporting files are NOT loaded automatically.

**Step 5: Document in CLAUDE.md**

After creating a skill, add a brief entry: skill name, trigger phrases, what it does, output location.

**Step 6: Test**

1. Natural language -- Say something matching the description. Does Claude load the skill?
2. Direct invocation -- Run /skill-name with test arguments. Verify $ARGUMENTS substitutes correctly.
3. Edge cases -- Try missing arguments, unusual input, empty input.
4. Character budget -- Run /context to confirm skill description is loaded if you have many skills.

---

## Mode 2: Audit an Existing Skill

Read the skill file first. Then run through this checklist and fix issues before marking the audit complete.

### Frontmatter Audit

- [ ] name matches the directory name
- [ ] description uses natural keywords someone would actually say
- [ ] description is specific enough to avoid false triggers but broad enough to catch real requests
- [ ] disable-model-invocation: true is set if the skill has side effects
- [ ] argument-hint is set if the skill accepts arguments via /name
- [ ] allowed-tools is set if the skill should NOT have access to all tools
- [ ] context: fork is used if the skill is self-contained and produces verbose output
- [ ] model is set only if a specific model capability is needed
- [ ] No unnecessary fields are set

### Content Audit

- [ ] Total SKILL.md is under 500 lines
- [ ] Clear step-by-step workflow with numbered steps (for task skills)
- [ ] Output format is specified with templates or examples
- [ ] All file paths and locations are documented
- [ ] Agent delegation instructions include the actual prompt text to send
- [ ] Notes section covers edge cases, constraints, and what NOT to do
- [ ] No vague instructions -- every step tells Claude exactly what to do
- [ ] String substitutions ($ARGUMENTS, $N) are used where the skill takes input

### Integration Audit

- [ ] Skill is documented in CLAUDE.md
- [ ] Supporting files (if any) are referenced from SKILL.md, not orphaned
- [ ] Scripts (if any) have correct file paths and are executable
- [ ] API keys (if any) are stored in environment variables, never hardcoded

### Quality Audit

- [ ] A beginner could follow the instructions without prior context
- [ ] Instructions are actionable, not abstract
- [ ] Delegates to subagents when appropriate to keep main context clean
- [ ] Doesn't duplicate information that lives elsewhere
- [ ] Output paths follow a predictable convention

### Optimization Opportunities

After running the audit, check [reference.md](reference.md) for advanced features: context: fork, allowed-tools, dynamic context injection, hooks, and supporting files.

---

## Recommended Conventions

- Skills live in .claude/skills/[skill-name]/SKILL.md
- Output files go in output/[skill-name]/
- API keys go in environment variables, never hardcoded in skill files
- Document all active skills in CLAUDE.md
- Frontmatter description is written as: "Use when someone asks to [action], [action], or [action]."

## Important Notes

- Always read an existing skill before optimizing it. Never propose changes to a skill you haven't read.
- When building a new skill, check if a similar skill already exists that could be extended instead.
- For advanced patterns (subagent execution, hooks, permissions), see [reference.md](reference.md).
