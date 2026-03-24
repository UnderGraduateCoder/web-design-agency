"""
find_hero_video.py

Usage:
    python tools/find_hero_video.py
    python tools/find_hero_video.py --query "textile factory"   # override search query

Reads .tmp/business_info.json, maps the industry to an optimised video search
query, and downloads an HD/4K stock video from **Pexels** to use as the hero
background.  Updates business_info.json with `hero_video_url` and
`hero_video_poster`.

Requires:
    PEXELS_API_KEY in .env  — Free at https://www.pexels.com/api/
"""

import sys
import json
import os
import re
import argparse
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Industry → video search query mapping
# ---------------------------------------------------------------------------

INDUSTRY_VIDEO_QUERIES = {
    # Legal
    "immigration law": "law firm office interior professional",
    "law": "law office books professional",
    # Trades
    "hvac": "air conditioning technician professional",
    "plumbing": "plumbing pipes water professional",
    "electrical": "electrician wiring professional",
    "construction": "construction site building",
    "roofing": "rooftop aerial view houses",
    "landscaping": "garden landscaping green plants",
    "cleaning": "clean modern interior sunlight",
    # Health
    "medical": "medical clinic hospital modern",
    "dental": "dental clinic modern bright",
    # Food & Drink
    "restaurant": "restaurant interior dining elegant",
    "cafe": "coffee shop barista latte",
    "bakery": "bakery fresh bread artisan",
    # Fitness & Wellness
    "fitness": "gym workout equipment modern",
    "yoga": "yoga studio peaceful meditation",
    # Beauty
    "beauty": "beauty salon hairdresser styling",
    # Real Estate
    "real estate": "luxury home exterior architecture",
    # Creative
    "photography": "photography studio camera professional",
    # Professional Services
    "accounting": "office business professional desk",
    "consulting": "business meeting boardroom professional",
    "insurance": "corporate office professional trust",
    "financial": "finance office city skyline",
    # Tech
    "tech": "technology digital abstract futuristic",
    "software": "programming code technology abstract",
    "marketing": "creative agency workspace modern",
    # Education
    "education": "classroom learning students modern",
    "tutoring": "study books learning bright",
    "childcare": "children playing colorful nursery",
    # Other
    "pet": "veterinary pet clinic animals",
    "automotive": "auto repair workshop mechanic",
    "logistics": "warehouse logistics shipping professional",
    "security": "security monitoring technology",
    # Textile / Manufacturing (product-focused, no people — avoids cultural mismatch with local businesses)
    "textile": "fabric rolls colorful textile close up",
    "manufacturing": "factory machinery production line industrial",
    "fabric": "fabric rolls colorful textile close up",
    "clothing": "fashion fabric sewing machine close up",
    "confecciones": "fashion fabric sewing machine close up",
    "tejidos": "fabric rolls colorful textile close up",
    "garment": "fashion fabric sewing machine close up",
}

DEFAULT_QUERY = "professional business office modern"


def slugify(text: str) -> str:
    """Convert text to a safe, lowercase filename slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-") or "business"


def get_video_query(industry: str) -> str:
    """Match industry string to a search query (fuzzy)."""
    industry_lower = industry.lower()
    for key, query in INDUSTRY_VIDEO_QUERIES.items():
        if key in industry_lower or industry_lower in key:
            return query
    return DEFAULT_QUERY


# ---------------------------------------------------------------------------
# Pexels Video API
# ---------------------------------------------------------------------------

PEXELS_API_URL = "https://api.pexels.com/videos/search"

# Quality thresholds
MIN_WIDTH = 1920
MIN_HEIGHT = 1080
MIN_DURATION = 3    # seconds
MAX_DURATION = 30   # seconds
MAX_FILE_SIZE_MB = 15
MIN_FILE_SIZE_KB = 500


def search_pexels_videos(query: str, api_key: str, per_page: int = 15) -> list:
    """Search Pexels for videos matching the query. Returns raw API results."""
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": "landscape",
        "size": "large",
    }

    print(f"  Searching Pexels: \"{query}\" ...")
    try:
        resp = requests.get(PEXELS_API_URL, headers=headers, params=params, timeout=15)
    except requests.RequestException as e:
        print(f"  Error calling Pexels API: {e}")
        return []

    if resp.status_code == 401:
        print("  Error: Invalid PEXELS_API_KEY. Get a free key at https://www.pexels.com/api/")
        return []
    if resp.status_code != 200:
        print(f"  Error: Pexels returned HTTP {resp.status_code}")
        return []

    data = resp.json()
    videos = data.get("videos", [])
    print(f"  Found {len(videos)} videos")
    return videos


def select_best_video(videos: list) -> dict | None:
    """
    From a list of Pexels video results, pick the best one for a hero background.

    Selection criteria:
    1. Landscape orientation (width > height)
    2. Duration between MIN_DURATION and MAX_DURATION
    3. Has an HD or higher quality video file (>= 1920px wide)
    4. Prefer shorter videos (better for looping)
    5. Prefer higher resolution

    Returns a dict with keys: video_url, width, height, poster_url, duration, file_size
    or None if no suitable video found.
    """
    candidates = []

    for video in videos:
        duration = video.get("duration", 0)
        if duration < MIN_DURATION or duration > MAX_DURATION:
            continue

        width = video.get("width", 0)
        height = video.get("height", 0)
        if width <= height:
            # Skip portrait videos
            continue

        # Find the best video file (HD or higher)
        video_files = video.get("video_files", [])
        best_file = None
        best_width = 0

        for vf in video_files:
            fw = vf.get("width") or 0
            fh = vf.get("height") or 0
            file_type = vf.get("file_type", "")

            if "mp4" not in file_type:
                continue
            if fw < MIN_WIDTH:
                continue
            if fw <= fh:
                continue

            # Prefer HD (1920) over 4K (3840) to keep file size reasonable
            # but still pick 4K if that's all we have
            if best_file is None or (fw >= MIN_WIDTH and fw < best_width) or best_width < MIN_WIDTH:
                if fw >= MIN_WIDTH:
                    best_file = vf
                    best_width = fw

        if not best_file:
            continue

        # Get poster image (thumbnail)
        poster_url = ""
        video_pictures = video.get("video_pictures", [])
        if video_pictures:
            poster_url = video_pictures[0].get("picture", "")

        candidates.append({
            "video_url": best_file.get("link", ""),
            "width": best_file.get("width", 0),
            "height": best_file.get("height", 0),
            "poster_url": poster_url,
            "duration": duration,
            "file_size": best_file.get("size", 0),
            "quality": best_file.get("quality", ""),
        })

    if not candidates:
        return None

    # Sort: prefer shorter duration (better loops), then higher resolution
    candidates.sort(key=lambda c: (c["duration"], -c["width"]))

    best = candidates[0]
    print(f"  Selected: {best['width']}x{best['height']}, {best['duration']}s, "
          f"~{best['file_size'] / 1024 / 1024:.1f} MB")
    return best


def download_video(url: str, output_path: Path) -> bool:
    """Download video file with progress indication. Returns True on success."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"  Downloading video ...")
    try:
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Error downloading video: {e}")
        return False

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0

    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = downloaded / total * 100
                print(f"\r  Progress: {pct:.0f}% ({downloaded / 1024 / 1024:.1f} MB)", end="", flush=True)

    print()  # newline after progress

    size_kb = downloaded / 1024
    if size_kb < MIN_FILE_SIZE_KB:
        print(f"  Warning: Downloaded file is only {size_kb:.0f} KB — possibly corrupted. Removing.")
        output_path.unlink(missing_ok=True)
        return False

    print(f"  Saved: {output_path} ({size_kb / 1024:.1f} MB)")
    return True


def download_poster(url: str, output_path: Path) -> bool:
    """Download poster/thumbnail image. Returns True on success."""
    if not url:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Warning: Could not download poster: {e}")
        return False

    with open(output_path, "wb") as f:
        f.write(resp.content)

    print(f"  Poster saved: {output_path} ({len(resp.content) / 1024:.0f} KB)")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Find and download a hero video from Pexels")
    parser.add_argument("--query", type=str, default=None,
                        help="Override the automatic industry-based search query")
    args = parser.parse_args()

    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        print("Error: PEXELS_API_KEY not set in .env")
        print("Get a free API key at https://www.pexels.com/api/")
        sys.exit(1)

    info_path = Path(".tmp/business_info.json")
    if not info_path.exists():
        print("Error: .tmp/business_info.json not found.")
        print("Run gather_business_info.py first.")
        sys.exit(1)

    with open(info_path, encoding="utf-8") as f:
        business_info = json.load(f)

    industry = business_info.get("industry", "business")
    business_name = business_info.get("business_name", "")

    # Determine search query
    if args.query:
        query = args.query
        print(f"Using custom query: \"{query}\"")
    else:
        query = get_video_query(industry)
        print(f"Industry: {industry}")
        print(f"Auto query: \"{query}\"")

    # Search
    videos = search_pexels_videos(query, api_key)
    if not videos:
        print("\nNo videos found. Try a different query with --query \"your terms\"")
        sys.exit(0)

    # Select best
    best = select_best_video(videos)
    if not best:
        print("\nNo videos met quality criteria (HD, landscape, 3-30s).")
        print("Try a broader query with --query \"your terms\"")
        sys.exit(0)

    # Download video
    slug = slugify(business_name) if business_name else "business"
    video_filename = f"{slug}_hero.mp4"
    video_path = Path(f"output/assets/{video_filename}")

    success = download_video(best["video_url"], video_path)
    if not success:
        print("\nFailed to download video.")
        sys.exit(1)

    # Download poster image
    poster_filename = f"{slug}_hero_poster.jpg"
    poster_path = Path(f"output/assets/{poster_filename}")
    poster_saved = download_poster(best["poster_url"], poster_path)

    # Update business_info.json
    business_info["hero_video_url"] = f"assets/{video_filename}"
    if poster_saved:
        business_info["hero_video_poster"] = f"assets/{poster_filename}"

    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(business_info, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] business_info.json updated")
    print(f"  hero_video_url    : assets/{video_filename}")
    if poster_saved:
        print(f"  hero_video_poster : assets/{poster_filename}")
    print(f"  Resolution        : {best['width']}x{best['height']}")
    print(f"  Duration          : {best['duration']}s")
    print(f"\nNext step: python tools/build_website.py")


if __name__ == "__main__":
    main()
