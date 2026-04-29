---
name: client-onboarding
description: One-command client onboarding — creates DB record, generates contracts PDFs, creates workspace folders, sends welcome email with Calendly link, marks lead as won
argument-hint: "--lead-id 42 [--tier pro]"
---

# Client Onboarding

Takes a `lead_id` for a won deal and performs complete onboarding in a single command: creates the client in the database, generates both the service contract and security authorization PDFs, sets up all workspace folders, sends a welcome email with contracts attached and a Calendly link, and marks the lead as `won`.

## When to Invoke

- User says "onboard client", "cliente ganado", "won lead", "cerrar cliente"
- A lead has agreed to proceed and user wants to set everything up
- User asks to "send the contract" or "send the welcome email" to a specific lead
- Status transition: `in_conversation` → `won`

## Workflow

### Step 1 — Confirm the lead

Verify the `lead_id` exists and that there's agreement to proceed. If the lead is still `new` or `contacted`, flag it and ask for confirmation before continuing.

### Step 2 — Confirm the tier

If not provided, ask the user which plan was agreed: `basic` (690€), `pro` (1290€), `premium` (1990€), `enterprise` (3500€).

### Step 3 — Run onboarding tool

```bash
python tools/onboard_client.py --lead-id 42 --tier pro
```

The tool performs all 6 steps automatically:

1. **Create client in DB** — `create_client_from_lead(lead_id, tier)`
2. **Generate service contract PDF** — reads `templates/service_contract_template_es.md`, interpolates client data + tier pricing → `brand_assets/{slug}/service_contract_{date}.pdf`
3. **Generate authorization contract PDF** — reads `templates/authorization_contract_template.md` → `brand_assets/{slug}/authorization_contract_{date}.pdf`
4. **Create workspace folders**:
   - `brand_assets/{slug}/`
   - `output/websites/{slug}/`
   - `output/audits/{slug}/`
   - `output/quotes/{slug}/`
5. **Send welcome email** — both PDFs attached + Calendly link from `CALENDLY_URL` in `.env`
6. **Mark lead as won** — `update_lead_status(lead_id, "won")`

### Step 4 — Report to user

- Confirm client slug and DB ID
- List contracts created with paths
- Confirm folders created
- Confirm email sent (or WARN if no email on lead)
- Lead status: `won`

### Step 5 — Suggest next steps

Remind the user to:
- Wait for signed contracts — save to `brand_assets/{slug}/`
- Begin website build once contracts are signed
- Save signed auth contract as `brand_assets/{slug}/authorization_signed.pdf` before running security audits

## Edge Cases

- **No CALENDLY_URL in .env**: Tool uses placeholder `https://calendly.com/urdimbre`. Remind user to set it.
- **No email on lead**: Welcome email skipped with warning. Contracts still generated.
- **WeasyPrint not installed**: Contracts saved as HTML. User prints to PDF from browser.
- **Client slug already exists in DB**: May raise integrity error. Handle by confirming the slug or updating the existing record.
- **Lead already won**: Tool is idempotent — folders are created if missing, new date-stamped contracts are generated, email is re-sent.
