---
name: ab-testing
description: Enterprise-only A/B variant testing — deploys two HTML variants with inline JS beacon, collects conversion events via Flask endpoint, auto-promotes winner after 14 days or 1000 visitors.
version: 1.0.0
triggers: [/ab-testing]
argument-hint: "[client_slug] [test_name] [variant_a_path] [variant_b_path]"
---

# Skill: ab-testing

Deploys two HTML variants to a client's site with 50/50 random assignment, cookie stickiness, and conversion event tracking. Auto-promotes the winning variant after 14 days or 1000 unique visitors.

---

## HARD RULE — Enterprise tier only

**This skill is restricted to enterprise-tier clients only.**

Before proceeding with ANY action, check:
```python
import tools.db as db
client = db.get_client(slug)
if client["tier"] != "enterprise":
    # REJECT — do not proceed
```

If the client is not on the enterprise tier, respond:  
> "Las pruebas A/B están disponibles exclusivamente en el plan Enterprise. El cliente actual está en el plan [tier]. ¿Deseas gestionar una actualización de plan?"

Do not create tests, run the deploy script, or start the beacon for non-enterprise clients.

---

## When to invoke

MUST invoke when the user:
- Asks to run, set up, or analyze an A/B test for a client
- Uses phrases like "prueba A/B", "test de variantes", "probar dos versiones", "cuál convierte más"
- Asks to compare two hero sections, CTAs, or page variants

---

## Architecture

```
deploy_ab_test.py          →  Creates AB test in DB + generates instrumented HTML
ab_test_beacon.py (Flask)  →  Receives pageview/conversion events → logs to ab_test_events
                            →  After 14 days or 1000 visitors: auto-promotes winner + generates report
```

---

## Step 1 — Start the beacon endpoint

The beacon must be running BEFORE deploying the test:

```bash
# Start beacon (runs on port from AB_BEACON_PORT env var, default 5050)
python tools/ab_test_beacon.py

# Or in background:
nohup python tools/ab_test_beacon.py > output/ab_tests/beacon.log 2>&1 &
```

Health check: `curl http://localhost:5050/health`

## Step 2 — Deploy the test

```bash
python tools/deploy_ab_test.py \
  --client-slug enterprise-client \
  --test-name "Hero variante agosto" \
  --variant-a path/to/variant_a.html \
  --variant-b path/to/variant_b.html
```

Variant inputs can be file paths OR raw HTML strings.

**Output:** `output/ab_tests/{slug}/{test_id}_deployed.html`

This is the instrumented snippet to embed in the client's site.

## Step 3 — Embed the snippet

Replace the target section in the client's `index.html` with the contents of `{test_id}_deployed.html`.

The inline JS handles:
- 50/50 random assignment on first visit
- Cookie stickiness (`abt_{test_id}=A|B`, 30-day expiry)
- Automatic `pageview` event on load
- `window.abTrack("conversion")` for manual conversion tracking

**To fire a conversion event from a CTA button:**
```html
<button onclick="window.abTrack('conversion')">Solicitar presupuesto</button>
```

## Step 4 — Monitor events

```bash
# Check event counts
python -c "import tools.db as db; events = db.get_ab_test_events(TEST_ID); print(len(events), 'events')"

# Live tail beacon logs
tail -f output/ab_tests/beacon.log
```

## Auto-promotion trigger

After **14 days** OR **1000 unique visitors** (whichever comes first), the beacon:

1. Determines winner by conversion rate (conversions / pageviews per variant)
2. Calls `db.end_ab_test(test_id, winner)`
3. Generates Spanish PDF report at `output/ab_tests/{slug}/{test_id}_report.pdf`

**Tie threshold:** < 2 percentage-point difference → declares tie, keeps variant A.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `AB_BEACON_PORT` | `5050` | Flask beacon listen port |
| `AB_BEACON_URL` | `http://localhost:5050` | Public URL embedded in JS (set to production URL if client site is live) |

---

## DB tables used

| Table | Purpose |
|---|---|
| `ab_tests` | One row per test (variants, status, winner, dates) |
| `ab_test_events` | One row per beacon event (pageview or conversion) |

---

## Report PDF

**Location:** `output/ab_tests/{slug}/{test_id}_report.pdf`

**Title:** "Informe A/B — {test_name} — {cliente}"

**Contents:** conversion rate A vs B, lift %, winner badge, test duration, unique visitor count. Same Copper/WeasyPrint design language as audit and quote PDFs.

---

## Agent workflow

1. Verify enterprise tier — hard reject if not
2. Confirm beacon is running (`curl http://localhost:5050/health`)
3. Run `deploy_ab_test.py` with client_slug, test_name, and both variants
4. Report test_id, deployed HTML path, and instructions for embedding + conversion tracking
5. After test ends (auto or manual): summarize report PDF findings to user
