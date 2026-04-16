# Workflow: Security Audit Service

## Objective

Deliver a professional, AI-powered security audit report to a client as a paid service. This workflow uses Anthropic's Claude to analyze a client's codebase for security vulnerabilities — then produces a structured Spanish-language report the client can act on. No system is ever scanned without a signed authorization contract on file.

---

## Prerequisites

- `ANTHROPIC_API_KEY` set in `.env`
- `git` installed and accessible in PATH
- Python packages: `anthropic`, `python-dotenv` (via `pip install -r requirements.txt`)
- A signed authorization contract from the client (see Step 1 below — this is mandatory)

---

## Required Inputs

| Input | Description |
|---|---|
| `client_slug` | URL-safe client identifier, e.g. `acme-corp` |
| `target` | GitHub repo URL (`https://github.com/client/repo`) or local path |
| Signed contract | PDF at `brand_assets/{client_slug}/authorization_signed.pdf` |

---

## Expected Outputs

| Output | Path |
|---|---|
| Structured findings | `output/audits/{client_slug}/findings.json` |
| Client report (rendered) | `output/audits/{client_slug}/report.md` |
| Signed contract (on file) | `brand_assets/{client_slug}/authorization_signed.pdf` |

---

## Phase 1 — Authorization (MANDATORY — do not skip)

### Step 1 — Send the Authorization Contract
1. Fill in `templates/authorization_contract_template.md` with the client's details
2. Send to client for signature (DocuSign, HelloSign, or physical signature scanned as PDF)
3. Receive the signed PDF back from the client
4. Save it to `brand_assets/{client_slug}/authorization_signed.pdf`

**This step is a hard gate. `tools/security_audit.py` will abort immediately if the signed PDF is not on file. Never skip this step for any client engagement.**

---

## Phase 2 — Run the Audit

### Step 2 — Execute the Security Audit Tool
```bash
python tools/security_audit.py \
  --target https://github.com/client/repo \
  --client-slug acme-corp
```

For a local target:
```bash
python tools/security_audit.py \
  --target /path/to/local/repo \
  --client-slug acme-corp
```

**What it does:**
1. Verifies `brand_assets/{client_slug}/authorization_signed.pdf` exists — aborts if missing
2. If target is a URL: clones the repo into `.tmp/audit_{client_slug}/` (depth 1)
3. Walks the codebase, collecting all scannable source files (Python, JS, TS, Go, etc.)
4. Sends the codebase context to Claude with Anthropic's official security audit prompt
5. Parses the structured JSON response
6. Writes `output/audits/{client_slug}/findings.json`
7. Cleans up the temporary clone

**Excluded from scan (by design — Anthropic's framework exclusions):**
- DoS / resource exhaustion vulnerabilities
- Outdated third-party library versions
- Rate limiting recommendations
- Memory leaks or CPU exhaustion
- Disk-stored secrets (handled by separate processes)

---

## Phase 3 — Render the Client Report

### Step 3 — Generate Spanish-Language Report
Open `templates/audit_report_template.md` and populate it from `output/audits/{client_slug}/findings.json`. Save the completed report to `output/audits/{client_slug}/report.md`.

All findings must include:
- Severity (Alta / Media / Baja)
- Affected file(s) and line numbers
- Description of the vulnerability
- Exploit scenario
- Recommended remediation

The report must be entirely in Spanish.

---

## Severity Thresholds

| Severity | Spanish Label | Definition | Recommended Action |
|---|---|---|---|
| HIGH | Alta | Directly exploitable: RCE, auth bypass, data breach | Remediate before any deployment |
| MEDIUM | Media | Significant impact requiring specific conditions | Remediate within current sprint |
| LOW | Baja | Defense-in-depth / lower-impact improvements | Schedule in backlog |

---

## Interactive Mode — `/security-review` Slash Command

For ad-hoc audits inside Claude Code (no authorization contract required for self-audits on this project):

```
/security-review
```

This runs Anthropic's official interactive three-phase security review on the current working directory — examining git diffs, file contents, and data flows. Results are presented in-conversation, not saved to a JSON file. Use this for internal audits or as a pre-audit exploration before running `tools/security_audit.py` on a client repo.

---

## Full Run Example

```bash
# 1. Confirm contract is on file
ls brand_assets/acme-corp/authorization_signed.pdf

# 2. Run the audit
python tools/security_audit.py \
  --target https://github.com/acme-corp/web-app \
  --client-slug acme-corp

# 3. Check findings
cat output/audits/acme-corp/findings.json

# 4. Render the report
# Fill in templates/audit_report_template.md from findings.json
# Save to output/audits/acme-corp/report.md
```

---

## Pricing Reference

See `templates/audit_report_template.md` — Section 6 "Niveles de Servicio y Precios" for the pricing tiers to present to clients:
- **Corrección única**: One-time fix engagement — billed per finding severity
- **Mantenimiento mensual**: Monthly retainer — ongoing vulnerability monitoring

---

## API Cost Estimate

- Tool uses `claude-sonnet-4-6` at ~$3/M input tokens + $15/M output tokens
- A typical 50-file codebase sends ~80K tokens → roughly $0.24–$0.40 per scan
- Large codebases (>200 files) will be sampled at 120K char limit automatically

---

## Known Constraints / Lessons Learned

- The tool sends a representative sample (up to 120K chars) if the codebase is large — for very large repos, consider scoping the `--target` to a specific subdirectory
- `git clone --depth 1` is used for speed; this means only the latest commit is analyzed (no history)
- If Claude returns malformed JSON, the tool retries up to 3 times with the same prompt — this is usually sufficient
- Always verify the contract PDF is at the exact path `brand_assets/{client_slug}/authorization_signed.pdf` — the script checks this literally, no fuzzy matching
- The `/security-review` slash command requires git to be initialized in the project root (it uses `git diff` and `git log` internally)
