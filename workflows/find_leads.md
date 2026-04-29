# Workflow: Find Local Business Leads

**Objective:** Find local businesses with no website, a broken site, or an abandoned domain — qualified leads for cold outreach.

## Prerequisites
- `GOOGLE_PLACES_API_KEY` in `.env` (standard Google Cloud account, NOT Google AI Pro)
- Python 3.9+, `pip install -r requirements.txt`

## One-Time API Setup
1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create project → enable billing ($200 free credit/month)
2. APIs & Services → Library → enable **Places API** (standard, not "Places API New")
3. Credentials → Create API Key → restrict to Places API
4. Add to `.env`: `GOOGLE_PLACES_API_KEY=AIza...`

## Running
```bash
python tools/find_local_leads.py "industry" "city, country"

# Examples
python tools/find_local_leads.py "electricians" "Madrid, Spain"
python tools/find_local_leads.py "fontaneros" "Valencia, España"
python tools/find_local_leads.py "clínicas dentales" "Bilbao, España"
```
Fetches up to 60 results (3 pages × 20), checks website status for each.

## Outputs
| File | Contents |
|------|---------|
| `.tmp/qualified_leads.json` | Full structured data including `place_id` (use for `--place-id` in build_website workflow) |
| `output/leads.csv` | Business Name, Phone, Address, Website Status, Original URL, Google Maps Link |

## Lead Status Values
| Status | Meaning |
|--------|---------|
| `no_website` | No website on Google Maps — highest priority |
| `broken_website` | URL returns error or times out |
| `redirected_domain` | URL redirects to unrelated domain |

## After Getting Leads
1. Open `output/leads.csv` → sort by `Website Status` (`no_website` first)
2. Use `Google Maps Link` to look up business details
3. Run `build_website` workflow with `place_id` to create a demo site
4. Reach out with the demo as proof of concept

## Edge Cases
- Google Places only returns businesses with Google Maps listings — fully offline businesses won't appear
- 60 results = ~60 Place Details API calls = ~€1.02 per run (well within free tier)
- HTTP 403 responses can be false positives from bot-blocking — verify manually before outreach
- Spanish-language queries return more hyper-local results; English queries surface more internationally-optimized profiles
- 2-second delay between pages is a Google requirement handled automatically
