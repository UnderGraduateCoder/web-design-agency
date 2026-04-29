# Business Development & Client Operations Rules

Read this file before any lead/client/outreach work: `Read rules/biz-dev.md`

## Database Tables (`tools/db.py`)

Run `python tools/db.py --seed` to initialize tables.

| Table | Purpose |
|---|---|
| `leads` | Outbound pipeline (new → contacted → demo_sent → in_conversation → won/lost) |
| `outreach_log` | Email history per lead (sent_at, opened_at, replied_at) |
| `competitors` | Competitor URLs tracked per client |
| `competitor_scans` | Scan results (JSON) and PDF reports per competitor |
| `blog_posts` | Monthly blog records per client (draft/published/archived) |
| `ab_tests` | A/B test definitions with variant_a / variant_b and winner |
| `ab_test_events` | Per-session conversion events for running tests |
| `social_content_log` | Weekly social content log (post_count, output_path) |

Service contract template: `templates/service_contract_template_es.md` (Spanish, `{{PLACEHOLDER}}` syntax).

## External Communication — Hard Rule

Any skill sending email/WhatsApp/webhook MUST:
1. Log to the appropriate DB table **before** sending
2. Use `tools/email_sender.send_email()` — never raw `smtplib` or `requests`
3. Respect the **50 emails/sender/day** limit (`RateLimitError` raised if exceeded)
4. Use `dry_run=True` during development and testing

## Upcoming Skills (reserved, not yet implemented)

`outreach` · `competitor-tracker` · `blog-generator` · `ab-test-runner` · `social-content` · `whatsapp-widget` · `lead-scorer` · `demo-scheduler` · `billing-reminder` · `client-dashboard`
