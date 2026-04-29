"""
find_local_leads.py

Usage:
    python tools/find_local_leads.py "industry" "city, country"

Examples:
    python tools/find_local_leads.py "electricians" "Madrid, Spain"
    python tools/find_local_leads.py "fontaneros" "Barcelona, España"

Searches Google Maps for businesses matching the query, checks each one's
website status, and outputs qualified leads (no website / broken / redirected)
to .tmp/qualified_leads.json and output/leads.csv.

Requires GOOGLE_PLACES_API_KEY in .env.
"""

import sys
import io
import json
import csv
import re

# Ensure UTF-8 output on Windows (handles Spanish characters and box-drawing)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import os
import time
from pathlib import Path
from urllib.parse import urlparse

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

STATUS_NO_WEBSITE = "no_website"
STATUS_BROKEN = "broken_website"
STATUS_REDIRECTED = "redirected_domain"

JUNK_EMAIL_FRAGMENTS = [
    "example.com", "sentry.io", "w3.org", "schema.org",
    "cloudflare.com", "google.com", "wixpress.com", "wpengine.com",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_domain(url: str) -> str:
    """Return lowercase domain without www. prefix."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url.lower()


def check_website(url: str) -> str | None:
    """
    Check the HTTP status of a URL.

    Returns:
        STATUS_BROKEN       — connection error, timeout, or HTTP >= 400
        STATUS_REDIRECTED   — final domain differs from original domain
        None                — site is healthy (200–399, same domain)
    """
    original_domain = extract_domain(url)

    try:
        response = requests.get(
            url,
            headers=BROWSER_HEADERS,
            timeout=6,
            allow_redirects=True,
        )
    except requests.exceptions.RequestException:
        return STATUS_BROKEN

    if response.status_code >= 400:
        return STATUS_BROKEN

    final_domain = extract_domain(response.url)
    if final_domain and final_domain != original_domain:
        return STATUS_REDIRECTED

    return None  # healthy


_PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"
_PLACES_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.nationalPhoneNumber,places.websiteUri,places.rating,"
    "places.userRatingCount,places.businessStatus,"
    "places.editorialSummary,places.googleMapsUri"
)


def get_all_places(api_key: str, query: str) -> list[dict]:
    """Fetch up to 60 place results (3 pages) using Places API (New) searchText."""
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": _PLACES_FIELD_MASK,
    }
    all_results = []
    page_token = None

    for page_num in range(1, 4):
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

    return all_results


def extract_email_from_url(url: str, timeout: int = 5) -> str | None:
    """
    Try to find a contact email on a URL that is known to respond (redirected sites).
    Scans page HTML for mailto: links first, then plain email patterns in text.
    Returns the first non-junk email found, or None.
    """
    if not url:
        return None
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code >= 400:
            return None
        text = resp.text
        # 1. mailto: links (most reliable)
        mailto = re.search(
            r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
            text, re.IGNORECASE,
        )
        if mailto:
            email = mailto.group(1)
            if not any(junk in email.lower() for junk in JUNK_EMAIL_FRAGMENTS):
                return email
        # 2. Plain email patterns in text
        matches = re.findall(r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b', text)
        filtered = [e for e in matches if not any(junk in e.lower() for junk in JUNK_EMAIL_FRAGMENTS)]
        return filtered[0] if filtered else None
    except Exception:
        return None




# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print("Usage: python tools/find_local_leads.py \"industry\" \"city, country\"")
        print('Example: python tools/find_local_leads.py "electricians" "Madrid, Spain"')
        sys.exit(1)

    industry = sys.argv[1]
    location = sys.argv[2]
    query = f"{industry} in {location}"

    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("Error: GOOGLE_PLACES_API_KEY not set.")
        print("See workflows/find_leads.md for step-by-step setup instructions.")
        sys.exit(1)

    print(f"\nSearching Google Maps: \"{query}\"")
    print("Fetching up to 60 results (3 pages)...\n")

    places = get_all_places(api_key, query)
    total_found = len(places)
    print(f"\nFound {total_found} businesses. Checking website status...\n")

    qualified_leads = []
    checked = 0

    for place in places:
        if not place:
            continue

        checked += 1
        name = place.get("displayName", {}).get("text", "Unknown")
        phone = place.get("nationalPhoneNumber", "")
        address = place.get("formattedAddress", "")
        website = place.get("websiteUri", "")
        maps_url = place.get("googleMapsUri", "")
        rating = place.get("rating")
        review_count = place.get("userRatingCount")
        business_status = place.get("businessStatus", "")
        editorial = place.get("editorialSummary", {})
        description = editorial.get("text", "") if isinstance(editorial, dict) else ""

        print(f"  [{checked}/{total_found}] {name}", end=" ... ", flush=True)

        # Skip permanently closed businesses — not valid prospects
        if business_status == "CLOSED_PERMANENTLY":
            print("CLOSED PERMANENTLY — skipping")
            continue

        if not website:
            status = STATUS_NO_WEBSITE
            email = None
            print(f"[NO WEBSITE]")
        else:
            result = check_website(website)
            if result is None:
                print("OK — skipping")
                continue
            status = result
            email = None
            # Redirected sites have accessible URLs that respond — try to find email.
            # Broken sites are unreachable, so we rely on the phone number instead.
            if status == STATUS_REDIRECTED:
                email = extract_email_from_url(website)
            label = {"broken_website": "BROKEN", "redirected_domain": "REDIRECTED"}.get(status, status.upper())
            email_info = f" | email: {email}" if email else ""
            print(f"[{label}] {website}{email_info}")

        qualified_leads.append({
            "business_name": name,
            "phone": phone,
            "address": address,
            "website_status": status,
            "original_url": website,
            "google_maps_link": maps_url,
            "place_id": place_id,
            "rating": rating,
            "review_count": review_count,
            "description": description,
            "email": email,
        })

    emails_found = sum(1 for l in qualified_leads if l.get("email"))
    print(f"\n{'-'*50}")
    print(f"  Total checked  : {checked}")
    print(f"  Qualified leads: {len(qualified_leads)}")
    print(f"    No website   : {sum(1 for l in qualified_leads if l['website_status'] == STATUS_NO_WEBSITE)}")
    print(f"    Broken site  : {sum(1 for l in qualified_leads if l['website_status'] == STATUS_BROKEN)}")
    print(f"    Redirected   : {sum(1 for l in qualified_leads if l['website_status'] == STATUS_REDIRECTED)}")
    if emails_found:
        print(f"    Emails found : {emails_found}")
    print(f"{'-'*50}\n")

    if not qualified_leads:
        print("No qualified leads found. Try a different industry or location.")
        sys.exit(0)

    # Sort: no_website first, then broken, then redirected
    order = {STATUS_NO_WEBSITE: 0, STATUS_BROKEN: 1, STATUS_REDIRECTED: 2}
    qualified_leads.sort(key=lambda x: order.get(x["website_status"], 9))

    # --- Save JSON ---
    Path(".tmp").mkdir(exist_ok=True)
    json_path = Path(".tmp/qualified_leads.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(qualified_leads, f, indent=2, ensure_ascii=False)
    print(f"[OK] JSON saved: {json_path}")

    # --- Save CSV ---
    Path("output").mkdir(exist_ok=True)
    csv_path = Path("output/leads.csv")
    csv_columns = [
        "Business Name",
        "Phone",
        "Address",
        "Rating",
        "Review Count",
        "Website Status",
        "Original URL",
        "Google Maps Link",
        "Description",
        "Email",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        writer.writeheader()
        for lead in qualified_leads:
            writer.writerow({
                "Business Name": lead["business_name"],
                "Phone": lead["phone"],
                "Address": lead["address"],
                "Rating": lead.get("rating", ""),
                "Review Count": lead.get("review_count", ""),
                "Website Status": lead["website_status"],
                "Original URL": lead["original_url"],
                "Google Maps Link": lead["google_maps_link"],
                "Description": lead.get("description", ""),
                "Email": lead.get("email", ""),
            })
    print(f"[OK] CSV saved: {csv_path}")
    print(f"\nOpen leads.csv in Excel or Google Sheets to start prospecting.")
    print("Tip: sort by 'Website Status' — 'no_website' leads are highest priority.")


if __name__ == "__main__":
    main()
