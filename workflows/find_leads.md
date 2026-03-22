# Workflow: Find Local Business Leads

## Objective
Search for local businesses in a given industry and location. Automatically qualify leads by filtering to businesses that have **no website**, a **broken website**, or a **redirected/abandoned domain** — i.e., businesses that need your services.

## Prerequisites
- Python 3.9+
- Dependencies installed: `pip install -r requirements.txt`
- `GOOGLE_PLACES_API_KEY` set in `.env` (see setup guide below)

## Required Inputs
- Industry / business type (e.g. `"electricians"`, `"fontaneros"`, `"peluquerías"`)
- Location (e.g. `"Madrid, Spain"`, `"Barcelona, España"`, `"Sevilla"`)

## Expected Outputs
- `.tmp/qualified_leads.json` — full structured lead data
- `output/leads.csv` — spreadsheet-ready file (Business Name, Phone, Address, Website Status, Original URL, Google Maps Link)

---

## One-Time Setup: Get Your Google Places API Key

> **Important:** Google AI Pro (student plan) is a completely separate product and does NOT include Maps Platform credits. You need a standard Google Cloud account.

### Steps

1. **Go to Google Cloud Console**
   Open [console.cloud.google.com](https://console.cloud.google.com) and sign in with your Google account.

2. **Create a new project**
   - Click the project dropdown at the top → **New Project**
   - Name it something like `WAT Lead Gen` → **Create**

3. **Enable billing** (required to activate free credits)
   - Go to **Billing** in the left sidebar
   - Link a credit card
   - You receive **$200 free credit per month** — you will NOT be charged unless you exceed this limit. At roughly €0.017 per Place Details call, $200 covers ~11,700 lookups/month.

4. **Enable the Places API**
   - Go to **APIs & Services → Library**
   - Search for `Places API`
   - Click **Places API** → **Enable**
   *(Use the standard "Places API", not "Places API (New)" — the `googlemaps` Python library works best with the standard version)*

5. **Create an API key**
   - Go to **APIs & Services → Credentials**
   - Click **Create Credentials → API Key**
   - Copy the key (starts with `AIza...`)

6. **Add the key to your `.env` file**
   ```
   GOOGLE_PLACES_API_KEY=AIza...
   ```

7. **(Recommended) Restrict the key**
   - In Credentials, click the key → **Restrict Key**
   - Under **API restrictions**, select **Restrict key** → choose **Places API**
   - Save — this prevents misuse if the key is ever exposed

---

## Running the Tool

```bash
python tools/find_local_leads.py "industry" "city, country"
```

### Examples

```bash
# English-language queries work well even in Spain
python tools/find_local_leads.py "electricians" "Madrid, Spain"
python tools/find_local_leads.py "hair salons" "Barcelona, Spain"

# Spanish-language queries also work
python tools/find_local_leads.py "fontaneros" "Valencia, España"
python tools/find_local_leads.py "carpinteros" "Sevilla, España"
python tools/find_local_leads.py "clínicas dentales" "Bilbao, España"
```

### What happens when you run it

1. The tool searches Google Maps for businesses matching your query
2. It fetches up to **60 results** (3 pages × 20, with 2s pause between pages as required by Google)
3. For each business, it checks the website status
4. Qualified leads (no site, broken site, or abandoned redirect) are saved to output files
5. Progress prints to the terminal so you can watch it work

---

## Understanding the Output

### Lead Status Values

| Status | Meaning | What to say to the client |
|--------|---------|--------------------------|
| `no_website` | No website listed on Google Maps at all | "I noticed you don't have a website yet..." |
| `broken_website` | Website URL exists but returns an error or times out | "Your website seems to be down..." |
| `redirected_domain` | URL redirects to a completely different domain | "Your website address redirects to an unrelated site..." |

### Output files

**`output/leads.csv`** — open directly in Excel or Google Sheets. Columns:
- `Business Name`
- `Phone`
- `Address`
- `Website Status` — one of the three values above
- `Original URL` — the URL on file (blank if no_website)
- `Google Maps Link` — direct link to their Google Maps listing

**`.tmp/qualified_leads.json`** — full data including place_id, for use in follow-up automation.

---

## Typical Workflow After Getting Leads

1. Open `output/leads.csv` in Google Sheets
2. Sort by `Website Status` — `no_website` leads are highest priority
3. Use the `Google Maps Link` to look up the business, find their phone/email
4. Run Phase 1 (`build_website` workflow) to create a demo site for a promising lead before reaching out
5. Reach out with the demo site as a proof of concept

---

## Edge Cases & Known Constraints

- **Google Places only returns businesses that have a Google Maps listing** — businesses with no online presence at all won't appear
- **The tool makes 1 Place Details API call per business** — 60 results = 60 Place Details calls = ~€1.02 per search run, well within the $200 free tier
- **Some businesses return HTTP 403 even with a working site** — this is a false positive from bot-blocking. The tool uses a browser User-Agent to minimise this, but occasional misclassification is normal. Always verify manually before reaching out.
- **`next_page_token` requires a 2-second delay** — this is a Google requirement, not a bug. The tool handles it automatically.
- **Spanish-language vs English queries** — both work, but Spanish queries for Spanish cities tend to return more hyper-local results. English queries surface more results that have Google Business Profiles optimised for tourists/international.

---

## Lessons Learned
*(Update this section as you discover new constraints or better approaches)*
