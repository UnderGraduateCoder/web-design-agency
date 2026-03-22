"""
extract_brand.py

Usage:
    python tools/extract_brand.py --domain example.com
    python tools/extract_brand.py          # reads domain from .tmp/business_info.json contact.email

Extracts the business's existing brand identity (logo + primary color) and merges it
into .tmp/business_info.json under the "brand" key.

Strategy:
  1. Brandfetch API (primary) — returns official logo + hex colors for a given domain.
  2. BeautifulSoup scraper (fallback) — scrapes the existing site for a favicon and
     the most common hex color in their CSS.

Requires:
  BRANDFETCH_API_KEY in .env  (free tier: 500 req/month — brandfetch.com/developers)

Optional (scraper fallback only):
  pip install beautifulsoup4
"""

import sys
import json
import os
import re
import argparse
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
    print("Error: 'requests' package not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


# ---------------------------------------------------------------------------
# Brandfetch
# ---------------------------------------------------------------------------

def fetch_from_brandfetch(domain: str) -> dict | None:
    """Call Brandfetch API and return brand data, or None on failure."""
    api_key = os.getenv("BRANDFETCH_API_KEY")
    if not api_key:
        print("Warning: BRANDFETCH_API_KEY not set — will try scraper fallback.")
        return None

    url = f"https://api.brandfetch.io/v2/brands/{domain}"
    headers = {"Authorization": f"Bearer {api_key}"}
    print(f"Calling Brandfetch API for domain: {domain}")

    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as e:
        print(f"Brandfetch request failed: {e}")
        return None

    if resp.status_code == 404:
        print(f"Brandfetch: no data found for domain '{domain}'.")
        return None
    if resp.status_code != 200:
        print(f"Brandfetch returned HTTP {resp.status_code} — falling back to scraper.")
        return None

    data = resp.json()

    # --- Logo ---
    logo_url = None
    logos = data.get("logos") or []
    for logo_entry in logos:
        formats = logo_entry.get("formats") or []
        for fmt in formats:
            if fmt.get("format") in ("png", "svg") and fmt.get("src"):
                logo_url = fmt["src"]
                break
        if logo_url:
            break

    # --- Primary color ---
    primary_color = None
    colors = data.get("colors") or []
    if colors:
        # Brandfetch lists colors by type; prefer "accent" then first available
        for c in colors:
            if c.get("type") == "accent" and c.get("hex"):
                primary_color = c["hex"]
                break
        if not primary_color:
            primary_color = colors[0].get("hex")

    if not logo_url and not primary_color:
        print("Brandfetch returned data but no usable logo or colors.")
        return None

    print(f"  Logo URL : {logo_url}")
    print(f"  Brand color: {primary_color}")
    return {"logo_url": logo_url, "primary_color": primary_color, "source": "brandfetch"}


# ---------------------------------------------------------------------------
# BeautifulSoup scraper fallback
# ---------------------------------------------------------------------------

def fetch_from_scraper(domain: str) -> dict | None:
    """Scrape the business's existing site for a favicon and dominant CSS hex color."""
    if not BS4_AVAILABLE:
        print("Warning: beautifulsoup4 not installed — cannot use scraper fallback.")
        print("  Run: pip install beautifulsoup4")
        return None

    base_url = f"https://{domain}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    print(f"Scraper fallback: fetching {base_url}")

    try:
        resp = requests.get(base_url, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Scraper could not reach {base_url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # --- Logo: priority-ordered search ---
    logo_url = None

    # 1. <meta property="og:image"> — standardized Open Graph, almost universally present
    og_tag = soup.find("meta", property="og:image")
    if og_tag and og_tag.get("content"):
        src = og_tag["content"]
        logo_url = src if src.startswith("http") else f"{base_url.rstrip('/')}/{src.lstrip('/')}"

    # 2. <link rel="apple-touch-icon"> — 180×180 PNG, standardized and reliable
    if not logo_url:
        tag = soup.find("link", rel=lambda r: r and "apple-touch-icon" in " ".join(r).lower())
        if tag and tag.get("href"):
            href = tag["href"]
            logo_url = href if href.startswith("http") else f"{base_url.rstrip('/')}/{href.lstrip('/')}"

    # 3. <link rel="icon"> or <link rel="shortcut icon"> — favicon fallback
    if not logo_url:
        for rel_val in ("icon", "shortcut icon"):
            tag = soup.find("link", rel=lambda r: r and rel_val in " ".join(r).lower())
            if tag and tag.get("href"):
                href = tag["href"]
                logo_url = href if href.startswith("http") else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                break

    # 4. <img> whose src/class/id contains "logo" — last resort
    if not logo_url:
        for img in soup.find_all("img"):
            src = img.get("src", "")
            classes = " ".join(img.get("class", []))
            img_id = img.get("id", "")
            if "logo" in (src + classes + img_id).lower():
                logo_url = src if src.startswith("http") else f"{base_url.rstrip('/')}/{src.lstrip('/')}"
                break

    # --- Color: extract most frequent hex from inline <style> and <link> CSS ---
    primary_color = None
    all_css_text = ""

    # Inline styles
    for style_tag in soup.find_all("style"):
        all_css_text += style_tag.get_text() + " "

    # Try to fetch first external stylesheet
    for link_tag in soup.find_all("link", rel=lambda r: r and "stylesheet" in " ".join(r).lower()):
        css_href = link_tag.get("href", "")
        css_url = css_href if css_href.startswith("http") else f"{base_url.rstrip('/')}/{css_href.lstrip('/')}"
        try:
            css_resp = requests.get(css_url, headers=headers, timeout=8)
            all_css_text += css_resp.text
            break  # one stylesheet is enough
        except requests.RequestException:
            continue

    if all_css_text:
        hex_colors = re.findall(r"#([0-9a-fA-F]{6})\b", all_css_text)
        # Filter out near-white and near-black, count frequency, pick top
        filtered = [
            f"#{h}" for h in hex_colors
            if h.lower() not in ("ffffff", "000000", "f5f5f5", "eeeeee", "333333", "666666")
        ]
        if filtered:
            from collections import Counter
            most_common = Counter(filtered).most_common(1)[0][0]
            primary_color = most_common

    if not logo_url and not primary_color:
        print("Scraper found no logo or brand color on the existing site.")
        return None

    print(f"  Logo URL (scraped)  : {logo_url}")
    print(f"  Color (scraped CSS) : {primary_color}")
    return {"logo_url": logo_url, "primary_color": primary_color, "source": "scraped"}


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert business name to a safe, lowercase filename slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)      # remove non-alphanumeric except hyphens/spaces
    text = re.sub(r"[\s_]+", "-", text)        # spaces/underscores → hyphens
    text = re.sub(r"-{2,}", "-", text)         # collapse multiple hyphens
    return text.strip("-") or "business"


# ---------------------------------------------------------------------------
# Logo download
# ---------------------------------------------------------------------------

def download_logo(logo_url: str, business_name: str = "") -> str | None:
    """Download the logo to output/assets/{slug}_logo.{ext} and return the local path."""
    if not logo_url:
        return None

    output_dir = Path("output/assets")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine file extension from URL
    parsed_path = urlparse(logo_url).path
    ext = Path(parsed_path).suffix.lower() or ".png"
    if ext not in (".png", ".svg", ".jpg", ".jpeg", ".webp", ".ico"):
        ext = ".png"

    slug = slugify(business_name) if business_name else "business"
    filename = f"{slug}_logo{ext}"
    local_path = output_dir / filename
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(logo_url, headers=headers, timeout=15)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(resp.content)
        print(f"  Logo saved: {local_path}")
        return f"assets/{filename}"
    except requests.RequestException as e:
        print(f"Warning: Could not download logo from {logo_url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------

def domain_from_email(email: str) -> str | None:
    """Extract domain from an email address."""
    if "@" in email:
        return email.split("@", 1)[1].strip().lower()
    return None


def domain_from_business_info() -> str | None:
    """Read .tmp/business_info.json and infer domain from contact.email."""
    info_path = Path(".tmp/business_info.json")
    if not info_path.exists():
        return None
    with open(info_path, encoding="utf-8") as f:
        data = json.load(f)
    email = data.get("contact", {}).get("email", "")
    return domain_from_email(email) if email else None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract brand identity (logo + color) for a business domain."
    )
    parser.add_argument(
        "--domain",
        metavar="DOMAIN",
        default=None,
        help="Business domain (e.g. example.com). If omitted, inferred from business_info.json.",
    )
    args = parser.parse_args()

    domain = args.domain
    if not domain:
        domain = domain_from_business_info()
        if not domain:
            print("Error: No domain provided and could not infer one from .tmp/business_info.json.")
            print("  Run: python tools/extract_brand.py --domain example.com")
            sys.exit(1)
        print(f"Domain inferred from business_info.json: {domain}")

    # Try Brandfetch first, fall back to scraper
    brand_data = fetch_from_brandfetch(domain)
    if not brand_data:
        print("Trying scraper fallback...")
        brand_data = fetch_from_scraper(domain)

    if not brand_data:
        print("Could not extract brand data from either Brandfetch or scraper.")
        print("business_info.json will not be updated.")
        sys.exit(0)

    # Download logo locally (needs business name for slug, so read it first)
    info_path = Path(".tmp/business_info.json")
    if not info_path.exists():
        print("Error: .tmp/business_info.json not found. Run gather_business_info.py first.")
        sys.exit(1)

    with open(info_path, encoding="utf-8") as f:
        business_info = json.load(f)

    business_name = business_info.get("business_name", "")
    logo_local = download_logo(brand_data.get("logo_url"), business_name)
    if logo_local:
        brand_data["logo_local_path"] = logo_local

    business_info["brand"] = brand_data

    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(business_info, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Brand data merged into {info_path}")
    print(f"  Source       : {brand_data.get('source')}")
    print(f"  Primary color: {brand_data.get('primary_color')}")
    print(f"  Logo local   : {brand_data.get('logo_local_path', 'not downloaded')}")
    print("\nNext step: python tools/generate_images.py  (or skip to generate_copy.py)")


if __name__ == "__main__":
    main()
