---
name: lead-prospecting
description: Find and qualify local businesses as sales leads using Google Places — scrapes, classifies website status, scores, and saves to DB
argument-hint: '"Madrid" "restaurantes" [--limit 20]'
---

# Lead Prospecting

Finds businesses in a given region + sector via Google Places API, classifies each one's website status (no_site / broken / outdated / modern), scores them 0–100, saves results to a CSV, and inserts them into the `leads` table via `add_lead()`.

## When to Invoke

- User says "prospect leads", "buscar clientes", "find businesses", "generar leads"
- User provides a region (city, province) + sector (industry type)
- User asks "what businesses in X need a website?"
- User wants to start a new outreach campaign for a specific market

## Workflow

### Step 1 — Confirm inputs

Ask for or extract:
- `region`: city or province (e.g. "Madrid", "Barcelona", "Sevilla")
- `sector`: industry in Spanish (e.g. "restaurantes", "fontaneros", "peluquerías")
- `limit`: optional, default 20

### Step 2 — Run prospecting tool

```bash
python tools/prospect_leads.py --region "Madrid" --sector "restaurantes" --limit 20
```

The tool:
1. Calls Google Places API (requires `GOOGLE_PLACES_API_KEY` in `.env`)
2. Classifies each business's website:
   - `no_site` — no website at all (highest priority)
   - `broken` — site returns errors or won't load
   - `outdated` — no HTTPS or missing viewport meta
   - `modern` — works fine (lowest priority)
3. Scores each lead 0–100 (website need + Google rating + review volume + email bonus)
4. Saves to `data/leads/{region}_{sector}_{date}.csv`
5. Inserts each into the `leads` table with `add_lead()`

### Step 3 — Report results

After the tool runs, report to the user:
- Total qualified leads found
- Breakdown by website status
- Top 5 leads by score (name, status, score)
- CSV path and DB confirmation

### Step 4 — Suggest next step

Recommend: "Run `demo-generator` for the top lead to create a personalized demo before outreach."

## Edge Cases

- **No GOOGLE_PLACES_API_KEY**: Tool aborts with clear message. Remind user to add it to `.env`.
- **0 qualified leads**: Google Places returned only modern/healthy sites. Suggest a different sector or expand to nearby cities.
- **Duplicate lead**: `add_lead()` may create a duplicate if same business name is re-prospected. Acceptable — review CSV and dedupe manually.
- **No email found**: Normal for no_site/broken leads. Phone is recorded instead. Outreach can still proceed via phone or LinkedIn.
