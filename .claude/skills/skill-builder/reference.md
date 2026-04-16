# Skill Builder — Technical Reference Guide

This document covers the complete frontmatter field reference, invocation control matrix, allowed-tools syntax, advanced patterns, hooks integration, and troubleshooting for Claude Code skills.

---

## Frontmatter Fields — Complete Reference

Every skill begins with a YAML frontmatter block between `---` delimiters. Only `name` and `description` are required. All other fields are optional — only add what you actually need.

```yaml
---
name: skill-name
description: Use when someone asks to [action], [action], or [action].
disable-model-invocation: true
argument-hint: [argument description]
context: fork
context-files:
  - path/to/file.md
allowed-tools:
  - Read
  - Write
  - Bash
model: claude-opus-4-5
---
```

### `name`
- **Required**
- Matches the directory name exactly
- Lowercase, hyphens only, max 64 characters
- Becomes the `/slash-command` (e.g., `name: meeting-notes` → `/meeting-notes`)

### `description`
- **Required**
- How Claude decides whether to auto-invoke the skill
- Write as: "Use when someone asks to [action], [action], or [action]."
- Include natural language keywords your users would actually say
- Too specific = Claude never triggers it; too broad = false triggers
- Keep under 200 characters

### `disable-model-invocation`
- **Type:** boolean (`true`)
- Prevents Claude from auto-invoking this skill from natural language
- Only invocable via `/skill-name` slash command
- Use when the skill: has side effects, costs money, generates files, sends API requests
- Default: false (skill can be auto-invoked)

### `argument-hint`
- **Type:** string
- Shows in the `/` autocomplete menu as a hint for what to provide
- Example: `argument-hint: "[topic or date]"` shows as `/meeting-notes [topic or date]`
- Use `$ARGUMENTS` in skill content to access what the user typed after `/skill-name`
- For multiple positional arguments, use `$1`, `$2`, `$3` etc.

### `context`
- **Type:** string
- `context: fork` — skill runs in a fresh context without conversation history
  - Use for self-contained tasks that produce verbose output
  - Prevents contaminating the main conversation context
- `context: fork+agent` — runs in isolated context AND in a subagent
  - The skill's output returns to main conversation as a single message
  - Best for long-running tasks, file generation, API workflows

### `context-files`
- **Type:** array of file paths
- Files automatically loaded into context when the skill is invoked
- Paths are relative to the project root
- Use for: style guides, data schemas, template files, reference docs the skill needs to function

### `allowed-tools`
- **Type:** array of tool names (or restricted format — see below)
- Restricts which Claude tools are available during skill execution
- If omitted: skill has access to ALL tools
- If set: skill ONLY has access to listed tools

### `model`
- **Type:** string (model ID)
- Override the default model for this skill
- Use when: skill requires vision (image reading), needs extended context, requires specific capability
- Available: `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5`
- Default: inherits from session/project settings

---

## Invocation Control Matrix

| Scenario | `disable-model-invocation` | Invocable via | Auto-triggers |
|---|---|---|---|
| Task with side effects (API calls, file writes) | `true` | `/skill-name` only | Never |
| Reference skill (applies knowledge passively) | omitted | Natural language + `/skill-name` | Yes, when triggered |
| Self-contained output task | omitted + `context: fork` | Natural language + `/skill-name` | Yes |
| User-only explicit workflow | `true` + `context: fork` | `/skill-name` only | Never |

**When to use `disable-model-invocation: true`:**
- Skill costs money (API credits, image generation)
- Skill has destructive side effects (overwrites files, sends messages)
- Skill should only run when explicitly requested
- Skill is part of a multi-step workflow where accidental triggering would cause issues

---

## `allowed-tools` Syntax

### Allow specific tools
```yaml
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
```

### Allow all tools (default — omit the field)
```yaml
# Simply don't include allowed-tools
```

### Allow everything except specific tools
Not directly supported — instead, list only what you want to allow.

### Common tool subsets

**Read-only research skill:**
```yaml
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
  - WebSearch
```

**File generation skill:**
```yaml
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
```

**Code review skill (no writes):**
```yaml
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
```

**Full access (leave field out — don't add this):**
```yaml
# No allowed-tools field = all tools available
```

---

## Dynamic Context Injection

Use `!command` in skill content to run a shell command and inject its output into the skill at load time. This lets you pull live data (git status, file contents, API responses) into the skill's context before Claude begins.

```markdown
## Current State

!git log --oneline -10

!cat package.json | head -30
```

**Rules:**
- Commands run in the project root
- Output is injected inline where the `!command` line appears
- Use for: current branch/status, reading config files, listing available scripts
- Keep commands fast (< 2s) — slow commands delay skill load

---

## Supporting Files Pattern

Skills can have supporting files alongside `SKILL.md`. These do NOT load automatically — they only load when Claude explicitly reads them.

**Directory structure:**
```
.claude/skills/my-skill/
  SKILL.md          ← loads when skill is invoked
  reference.md      ← loaded only when SKILL.md instructs Claude to read it
  examples/
    example-1.json  ← loaded only when referenced
    template.html   ← loaded only when referenced
```

**In SKILL.md, reference supporting files explicitly:**
```markdown
## Step 3: Check Reference

Before building, read [reference.md](reference.md) for the complete field list.
```

**Best uses for supporting files:**
- Lengthy reference docs that aren't needed on every invocation
- Example files, templates, schemas
- Data files used as input to the skill's process
- Version-specific docs that change independently of the skill logic

---

## Hooks Integration

Skills can trigger Claude Code hooks for pre/post processing. Configure hooks in `.claude/settings.json`, not in the skill file itself.

**Common hook patterns:**

### Pre-skill validation hook
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Skill",
      "hooks": [{
        "type": "command",
        "command": "node .claude/hooks/validate-skill-inputs.js"
      }]
    }]
  }
}
```

### Post-skill file formatting hook
```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write",
      "hooks": [{
        "type": "command",
        "command": "prettier --write $CLAUDE_FILE_PATH"
      }]
    }]
  }
}
```

**Hook environment variables available:**
- `$CLAUDE_FILE_PATH` — file path from Write/Edit tool calls
- `$CLAUDE_TOOL_NAME` — name of the tool being used
- `$CLAUDE_SESSION_ID` — current session identifier

---

## Advanced Patterns

### Multi-step skill with subagent delegation

For skills that produce large outputs or have long-running steps, delegate to a subagent to keep the main context clean:

```markdown
## Step 4: Generate Report

Delegate to the Agent tool with this exact prompt:
"Read all files matching output/**/*.json and produce a consolidated summary table..."

Return only the final table to the main conversation.
```

### Conditional skill behavior based on `$ARGUMENTS`

```markdown
## Steps

If $ARGUMENTS contains "dry-run":
1. Print what would happen without making changes
2. Do not write any files

Otherwise:
1. Execute the full workflow
2. Write outputs to output/$1/
```

### Skill chaining (skills invoking other skills)

A skill can instruct Claude to invoke another skill as a sub-step:

```markdown
## Step 2: Run Quality Check

Before proceeding, invoke the `verification-quality` skill on the generated output.
Only continue to Step 3 if the quality check passes.
```

### Reference skill pattern

Reference skills add knowledge rather than performing an action. They load whenever Claude detects the relevant context:

```markdown
---
name: typescript-conventions
description: Use when writing TypeScript code in this project. Provides coding conventions, naming patterns, and style rules.
---

## Naming Conventions
- Interfaces: PascalCase, no `I` prefix
- Types: PascalCase
- Functions: camelCase
...
```

---

## Character Budget & Description Loading

All skill descriptions are loaded every conversation to help Claude decide which skills to invoke. This means total description length matters.

**Budget guidance:**
- Each description: keep under 200 characters
- Total across all skills: aim for under 8,000 characters combined
- Run `/context` to see how much context your skill descriptions are using

**If your skills aren't triggering:**
1. Run `/context` — check if descriptions are being truncated
2. Shorten descriptions across all skills
3. Move keyword-heavy text from description into the skill content itself

---

## Troubleshooting

### Skill not triggering from natural language
- Check description uses keywords the user actually said
- Verify the skill is in `.claude/skills/[name]/SKILL.md` (correct path)
- Run `/context` to confirm the description is loaded (not truncated)
- Try `/skill-name` directly to confirm the skill loads at all

### `$ARGUMENTS` not substituting
- Verify the user typed `/skill-name [something]` — not just `/skill-name`
- Check that `$ARGUMENTS` appears in the skill content (case-sensitive)
- For positional args, use `$1`, `$2` — they split on spaces

### Skill triggers when it shouldn't
- Add `disable-model-invocation: true` to require explicit `/skill-name` invocation
- Make the description more specific/narrow

### Supporting file not loading
- Supporting files NEVER load automatically
- Add an explicit instruction in SKILL.md: "Read [filename.md](filename.md) before proceeding"
- Verify the file path is relative to the skill directory

### Skill output polluting conversation context
- Add `context: fork` to run the skill in an isolated context
- The skill's output still returns to the conversation, but the intermediate steps don't

### API key not found in skill
- API keys must be in `.env` at the project root
- Skills read them via Python scripts: `os.getenv('KEY_NAME')` after `load_dotenv()`
- Never hardcode secrets in SKILL.md or supporting files

### Skill too slow / large context
- Move reference material to supporting files — they load only when needed
- Use `context: fork+agent` to run heavy skills in a subagent
- Keep SKILL.md under 500 lines — trim to what's actually needed on each invocation
