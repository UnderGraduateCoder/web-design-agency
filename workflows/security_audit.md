# Workflow: Security Audit Service

**Objective:** Deliver a paid AI-powered security audit to a client. Never scan a system without a signed authorization contract on file.

## Prerequisites
- `ANTHROPIC_API_KEY` in `.env`, `git` installed
- Signed authorization PDF at `brand_assets/{client_slug}/authorization_signed.pdf`

## Phase 1 — Authorization (HARD GATE — never skip)
1. Fill `templates/authorization_contract_template.md` with client details
2. Have client sign (DocuSign, HelloSign, or scanned PDF)
3. Save signed PDF to `brand_assets/{client_slug}/authorization_signed.pdf`

`tools/security_audit.py` aborts immediately if the PDF is missing. No exceptions.

## Phase 2 — Run the Audit
```bash
python tools/security_audit.py \
  --target https://github.com/client/repo \
  --client-slug acme-corp

# Local target
python tools/security_audit.py --target /path/to/repo --client-slug acme-corp
```
Tool verifies contract → clones repo (depth 1) → collects source files → sends to Claude → writes `output/audits/{client_slug}/findings.json` → cleans up.

**Excluded from scan by design:** DoS, outdated libraries, rate limiting, memory leaks, disk-stored secrets.

## Phase 3 — Render the Client Report
Populate `templates/audit_report_template.md` from `findings.json`. Save to `output/audits/{client_slug}/report.md`.

Every finding must include: severity (Alta/Media/Baja), affected file + line numbers, description, exploit scenario, remediation. Report must be entirely in Spanish.

## Severity Thresholds
| Level | Label | Definition | Action |
|-------|-------|-----------|--------|
| HIGH | Alta | Directly exploitable: RCE, auth bypass, data breach | Fix before any deployment |
| MEDIUM | Media | Significant impact, specific conditions required | Fix within current sprint |
| LOW | Baja | Defense-in-depth improvements | Schedule in backlog |

## Interactive Mode — `/security-review`
```
/security-review
```
Runs Anthropic's interactive three-phase review on current working directory (no contract required for self-audits). Results in-conversation only; not saved to JSON.

## API Cost
- `claude-sonnet-4-6` at ~$3/M input + $15/M output
- Typical 50-file codebase: ~80K tokens = $0.24–$0.40 per scan
- Large repos (>200 files): sampled at 120K char limit automatically

## Known Constraints
- `git clone --depth 1` — only latest commit analyzed (no history)
- Contract path checked literally: `brand_assets/{client_slug}/authorization_signed.pdf`
- JSON parse failures: tool retries up to 3× automatically
- For very large repos, scope `--target` to a specific subdirectory
- `/security-review` requires git initialized in project root
