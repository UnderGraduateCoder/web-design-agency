---
name: cold-outreach
description: Send a personalized Spanish cold email to a lead — generates with Claude Haiku, includes demo URL if available, respects 50/day limit
argument-hint: "--lead-id 42 [--dry-run]"
---

# Cold Outreach

Takes a `lead_id`, generates a personalized cold email in Spanish using Claude Haiku (references sector, city, and specific website observation), optionally includes the demo URL, sends via `email_sender.py`, logs to the `outreach_log` table, and advances lead status to `contacted`.

## When to Invoke

- User says "send outreach", "cold email", "contactar lead", "enviar email a lead"
- User asks to start emailing a list of leads after prospecting
- User says "reach out to lead #N" or "contact {business_name}"
- After a demo is generated and user wants to send it to the prospect

## Workflow

### Step 1 — Confirm lead has email

Check that the lead has an email address. If not, abort and suggest collecting it via phone or LinkedIn first.

### Step 2 — Check daily send limit

The tool checks `data/email_log.jsonl` before sending. If today's count is ≥50, it aborts. Inform the user of the limit reset time (midnight UTC).

### Step 3 — Run outreach tool

```bash
# Live send
python tools/send_outreach_email.py --lead-id 42

# Test without sending (logs and updates DB, no real email)
python tools/send_outreach_email.py --lead-id 42 --dry-run
```

The tool:
1. Calls `get_lead(lead_id)` for business name, sector, region, website_status, email
2. Maps `website_status` → a specific one-sentence observation in Spanish
3. Checks for a demo at `output/demos/{slug}/index.html` — includes URL if found
4. Calls Claude Haiku to generate a <120-word professional Spanish cold email
5. Sends via `send_email()` (RESEND_API_KEY preferred, SMTP fallback)
6. Calls `add_outreach_log()` to record in DB
7. Calls `mark_lead_contacted()` to advance status

### Step 4 — Confirm and report

After the tool runs:
- Confirm: email sent (or dry_run logged)
- Show the subject line generated
- Lead status → `contacted`
- Suggest: "If no reply within 5 days, follow up or generate a commercial proposal."

## Email quality rules (enforced by prompt)

- Under 120 words
- Professional Spanish, no AI-slop phrases
- Single CTA: reply to schedule a 15-min call
- References: business name, sector, city, specific website problem
- No generic copy ("somos expertos en", "soluciones innovadoras")

## Edge Cases

- **No email on lead**: Abort with message. Suggest finding email via LinkedIn or calling.
- **Rate limit hit (≥50 today)**: Abort. Schedule remaining sends for tomorrow.
- **Claude API error**: Retry once. If still failing, show the user the prompt so they can draft manually.
- **Demo URL doesn't exist**: Send without the demo link — a simple intro email is still effective.
- **Lead already at demo_sent or beyond**: Send anyway (follow-up), but don't downgrade status.
