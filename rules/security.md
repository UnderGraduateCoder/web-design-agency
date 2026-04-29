# Security Audit Rules

Read this file before any security audit engagement: `Read rules/security.md`

## Hard Rules — No Exceptions

- **NEVER** scan any client system without a signed contract on file
- Signed contract must be at `brand_assets/{client_slug}/authorization_signed.pdf` — `tools/security_audit.py` aborts if missing
- All client-facing reports must be entirely in **Spanish**
- All findings must include: severity (Alta/Media/Baja), affected file + line numbers, specific remediation
- Never publish or disclose findings outside the engagement without written client consent
- `/security-review` = interactive self-audit (no contract required); `tools/security_audit.py` = programmatic client engagement
- `--skip-contract` only for auditing this project itself

## Engagement Workflow

1. Fill `templates/authorization_contract_template.md` → client signs → save to `brand_assets/{client_slug}/authorization_signed.pdf`
2. Run: `python tools/security_audit.py --target <url_or_path> --client-slug <slug>`
3. Render findings into `templates/audit_report_template.md` → deliver in Spanish

## Tool Locations

| File | Purpose |
|---|---|
| `tools/security_audit.py` | Programmatic runner (requires signed contract) |
| `workflows/security_audit.md` | Full engagement SOP |
| `templates/audit_report_template.md` | Client report template (Spanish) |
| `templates/authorization_contract_template.md` | Authorization form (must be signed before scan) |
| `security-review/` | Anthropic's official framework (do not modify) |
| `.claude/commands/security-review.md` | Interactive `/security-review` slash command |
