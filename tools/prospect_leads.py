"""
prospect_leads.py

Usage:
    python tools/prospect_leads.py --region "Madrid" --sector "restaurantes" [--limit 20]

Searches Google Places for businesses in a given region + sector, classifies
each one's website status, scores them 0–100, saves to
data/leads/{region}_{sector}_{date}.csv, and inserts each into the leads
table via add_lead().

Website status categories:
    no_site   — business has no website at all
    broken    — HTTP 4xx/5xx or connection failure
    outdated  — site loads but lacks HTTPS, viewport meta, or looks pre-2018
    modern    — HTTPS + responsive + recent build signals (lowest priority)

Score formula (0–100):
    - website_need:  no_site=40, broken=30, outdated=20, modern=5
    - rating:        (google_rating / 5) * 30
    - review_volume: min(review_count / 100, 1) * 20
    - email_bonus:   +10 if email found

Requires: GOOGLE_PLACES_API_KEY in .env
"""

import sys
import io
import os
import csv
import re
import time
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("Error: 'requests' not installed. Run: pip install -r requirements.txt")
    sys.exit(1)


sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.db import add_lead


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

JUNK_EMAIL_FRAGMENTS = [
    "example.com", "sentry.io", "w3.org", "schema.org",
    "cloudflare.com", "google.com", "wixpress.com", "wpengine.com",
]

STATUS_NO_SITE = "no_site"
STATUS_BROKEN = "broken"
STATUS_OUTDATED = "outdated"
STATUS_MODERN = "modern"

OUTDATED_SIGNALS = [
    "charset=iso-8859",
    'name="viewport"',  # absence of this means non-responsive
    "<table",
    "jQuery/1.",
    "jquery/1.",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return domain[4:] if domain.startswith("www.") else domain
    except Exception:
        return url.lower()


def _classify_website(url: str) -> str:
    """HEAD/GET the URL and return one of the four STATUS_* constants."""
    if not url:
        return STATUS_NO_SITE

    original_domain = _extract_domain(url)

    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=8, allow_redirects=True)
    except requests.exceptions.RequestException:
        return STATUS_BROKEN

    if resp.status_code >= 400:
        return STATUS_BROKEN

    final_domain = _extract_domain(resp.url)
    if final_domain and final_domain != original_domain:
        return STATUS_BROKEN  # redirected away — treat as broken for our purposes

    if not resp.url.startswith("https://"):
        return STATUS_OUTDATED

    html = resp.text.lower()
    if 'name="viewport"' not in html and "name='viewport'" not in html:
        return STATUS_OUTDATED

    if any(sig.lower() in html for sig in ["jquery/1.", "jquery-1.", "jquery.min.js/1"]):
        return STATUS_OUTDATED

    return STATUS_MODERN


def _find_email(url: str) -> str | None:
    """Scan page HTML for a contact email address."""
    if not url:
        return None
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=6, allow_redirects=True)
        if resp.status_code >= 400:
            return None
        text = resp.text
        mailto = re.search(
            r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
            text, re.IGNORECASE,
        )
        if mailto:
            email = mailto.group(1)
            if not any(junk in email.lower() for junk in JUNK_EMAIL_FRAGMENTS):
                return email
        matches = re.findall(r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b', text)
        filtered = [e for e in matches if not any(junk in e.lower() for junk in JUNK_EMAIL_FRAGMENTS)]
        return filtered[0] if filtered else None
    except Exception:
        return None


def _score(website_status: str, rating: float | None, review_count: int | None, has_email: bool) -> float:
    need = {STATUS_NO_SITE: 40, STATUS_BROKEN: 30, STATUS_OUTDATED: 20, STATUS_MODERN: 5}.get(website_status, 10)
    rating_score = ((rating or 0) / 5.0) * 30
    volume_score = min((review_count or 0) / 100.0, 1.0) * 20
    email_bonus = 10 if has_email else 0
    return round(min(need + rating_score + volume_score + email_bonus, 100), 1)


_PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"
_PLACES_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.nationalPhoneNumber,places.websiteUri,places.rating,"
    "places.userRatingCount,places.businessStatus"
)


def _get_all_places(api_key: str, query: str, limit: int) -> list:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": _PLACES_FIELD_MASK,
    }
    all_results = []
    page_token = None

    for page_num in range(1, 4):
        if len(all_results) >= limit:
            break
        body: dict = {"textQuery": query, "languageCode": "es", "maxResultCount": 20}
        if page_token:
            body["pageToken"] = page_token
        print(f"  Page {page_num} ...", end=" ", flush=True)
        try:
            resp = requests.post(_PLACES_API_URL, json=body, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            print(f"API error: {e}")
            break
        places = data.get("places", [])
        print(f"{len(places)} results")
        all_results.extend(places)
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return all_results[:limit]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(region: str, sector: str, limit: int = 20) -> list:
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("[ERROR] GOOGLE_PLACES_API_KEY not set in .env")
        sys.exit(1)

    query = f"{sector} en {region}"

    print(f"\n[Prospecting] {sector} — {region}")
    print(f"Query: \"{query}\" | Limit: {limit}\n")

    places = _get_all_places(api_key, query, limit)
    total = len(places)
    print(f"\nFound {total} businesses. Classifying websites...\n")

    leads = []

    for i, place in enumerate(places, 1):
        if not place:
            continue

        name = place.get("displayName", {}).get("text", "Unknown")
        phone = place.get("nationalPhoneNumber", "")
        address = place.get("formattedAddress", "")
        website = place.get("websiteUri", "")
        rating = place.get("rating")
        review_count = place.get("userRatingCount")
        biz_status = place.get("businessStatus", "")

        print(f"  [{i}/{total}] {name}", end=" ... ", flush=True)

        if biz_status == "CLOSED_PERMANENTLY":
            print("CLOSED — skip")
            continue

        ws = _classify_website(website)
        email = _find_email(website) if ws in (STATUS_BROKEN, STATUS_OUTDATED, STATUS_MODERN) else None
        score = _score(ws, rating, review_count, bool(email))

        status_label = {STATUS_NO_SITE: "NO SITE", STATUS_BROKEN: "BROKEN",
                        STATUS_OUTDATED: "OUTDATED", STATUS_MODERN: "MODERN"}.get(ws, ws.upper())
        print(f"[{status_label}] score={score}" + (f" | {email}" if email else ""))

        leads.append({
            "business_name": name,
            "region": region,
            "sector": sector,
            "phone": phone,
            "email": email,
            "website": website,
            "website_status": ws,
            "score": score,
            "address": address,
            "rating": rating,
            "review_count": review_count,
        })

    # Sort: no_site > broken > outdated > modern, then by score desc
    order = {STATUS_NO_SITE: 0, STATUS_BROKEN: 1, STATUS_OUTDATED: 2, STATUS_MODERN: 3}
    leads.sort(key=lambda x: (order.get(x["website_status"], 9), -x["score"]))

    # --- Save CSV ---
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_region = re.sub(r"[^a-z0-9]", "_", region.lower())
    safe_sector = re.sub(r"[^a-z0-9]", "_", sector.lower())
    csv_dir = Path("data/leads")
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / f"{safe_region}_{safe_sector}_{date_str}.csv"

    fieldnames = ["business_name", "region", "sector", "phone", "email",
                  "website", "website_status", "score", "address", "rating", "review_count"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)

    print(f"\n[OK] CSV saved: {csv_path}")

    # --- Insert into DB ---
    inserted = 0
    for lead in leads:
        try:
            add_lead(
                business_name=lead["business_name"],
                region=lead["region"],
                sector=lead["sector"],
                phone=lead["phone"] or None,
                email=lead["email"],
                website=lead["website"] or None,
                website_status=lead["website_status"],
                score=lead["score"],
                notes=f"rating={lead['rating']} reviews={lead['review_count']} address={lead['address']}",
            )
            inserted += 1
        except Exception as e:
            print(f"  [WARN] Could not insert {lead['business_name']}: {e}")

    print(f"[OK] {inserted}/{len(leads)} leads inserted into DB")

    # Summary
    print(f"\n{'─'*50}")
    print(f"  Total qualified : {len(leads)}")
    for status in [STATUS_NO_SITE, STATUS_BROKEN, STATUS_OUTDATED, STATUS_MODERN]:
        count = sum(1 for l in leads if l["website_status"] == status)
        if count:
            print(f"    {status:<12}: {count}")
    print(f"\n  Top 5 leads by score:")
    for lead in leads[:5]:
        print(f"    {lead['score']:>5.1f}  {lead['business_name']}  [{lead['website_status']}]")
    print(f"{'─'*50}\n")

    return leads


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prospect leads via Google Places")
    parser.add_argument("--region", required=True, help='e.g. "Madrid"')
    parser.add_argument("--sector", required=True, help='e.g. "restaurantes"')
    parser.add_argument("--limit", type=int, default=20, help="Max businesses to check (default: 20)")
    args = parser.parse_args()
    run(args.region, args.sector, args.limit)
