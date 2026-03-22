"""
find_email.py

Usage:
    python tools/find_email.py <url_or_domain>

Examples:
    python tools/find_email.py example.com
    python tools/find_email.py https://www.mibusiness.es

Given a URL or domain, tries to find a contact email by checking:
  1. The homepage
  2. /contact and /contacto
  3. /about and /nosotros

Scans each page for mailto: links first (most reliable), then falls back to
regex email patterns in the page text.

No API keys required. Uses only requests from requirements.txt.
"""

import sys
import re
from urllib.parse import urljoin, urlparse

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

# Common contact page paths to check after the homepage
CONTACT_PATHS = [
    "/contact",
    "/contacto",
    "/contact-us",
    "/about",
    "/nosotros",
    "/quienes-somos",
    "/sobre-nosotros",
]

# Email fragments that indicate a false positive (system/library emails)
JUNK_EMAIL_FRAGMENTS = [
    "example.com",
    "sentry.io",
    "w3.org",
    "schema.org",
    "cloudflare.com",
    "google.com",
    "wixpress.com",
    "wpengine.com",
    "amazonaws.com",
    "noreply",
    "no-reply",
    "donotreply",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_url(raw: str) -> str:
    """Ensure the input has an https:// scheme."""
    raw = raw.strip().rstrip("/")
    if not raw.startswith(("http://", "https://")):
        return f"https://{raw}"
    return raw


def fetch_page(url: str, timeout: int = 5) -> str | None:
    """Fetch a page and return its HTML text, or None on any error."""
    try:
        resp = requests.get(
            url,
            headers=BROWSER_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        if resp.status_code < 400:
            return resp.text
        return None
    except Exception:
        return None


def extract_emails_from_html(html: str) -> list[str]:
    """
    Extract unique, non-junk email addresses from an HTML page.
    Prioritizes mailto: links, then falls back to plain text regex.
    """
    # 1. mailto: links (most reliable)
    mailto_matches = re.findall(
        r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
        html,
        re.IGNORECASE,
    )

    # 2. Plain email patterns in text (broader but more false positives)
    plain_matches = re.findall(
        r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b',
        html,
    )

    seen = set()
    unique = []
    for email in mailto_matches + plain_matches:
        email_lower = email.lower()
        if email_lower in seen:
            continue
        seen.add(email_lower)
        if not any(junk in email_lower for junk in JUNK_EMAIL_FRAGMENTS):
            unique.append(email)

    return unique


def find_email(base_url: str) -> str | None:
    """
    Check the homepage and common contact paths for an email address.
    Returns the first valid email found, or None.
    """
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    # Build ordered list of pages to check (homepage first, then contact paths)
    pages = [base_url] + [urljoin(origin, path) for path in CONTACT_PATHS]

    # Check up to 4 pages total to keep things fast
    for url in pages[:4]:
        print(f"  Checking: {url}")
        html = fetch_page(url)
        if not html:
            continue
        emails = extract_emails_from_html(html)
        if emails:
            return emails[0]

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/find_email.py <url_or_domain>")
        print("Examples:")
        print("  python tools/find_email.py example.com")
        print("  python tools/find_email.py https://www.mibusiness.es")
        sys.exit(1)

    raw_input = sys.argv[1]
    url = normalize_url(raw_input)

    print(f"\nSearching for contact email on: {url}")
    print("Checking homepage + common contact pages (max 4 pages)...\n")

    email = find_email(url)

    print()
    if email:
        print(f"[FOUND] {email}")
    else:
        print("[NOT FOUND] No email address discovered on this domain.")
        print("Tip: Try running on the /contact or /contacto page directly.")

    return email


if __name__ == "__main__":
    main()
