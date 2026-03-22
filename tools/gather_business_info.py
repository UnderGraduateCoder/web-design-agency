"""
gather_business_info.py

Usage:
    python tools/gather_business_info.py "Your business description here"
    python tools/gather_business_info.py "Your business description here" --place-id ChIJ...

Calls Claude API to extract and infer structured business data from a plain-text
description. Writes .tmp/business_info.json. No interactive prompts — all missing
fields are inferred by the LLM.

Optional --place-id flag fetches real Google rating, review count, and top 5 reviews
from the Google Places API and merges them into business_info.json under the
"google_places" key.
"""

import sys
import json
import os
import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional; key can be set in the environment directly

try:
    import anthropic
except ImportError:
    print("Error: 'anthropic' package not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    import googlemaps
except ImportError:
    googlemaps = None


EXTRACTION_PROMPT = """You are extracting structured business information from a user's description to populate a professional website generator.

Given this business description:
"{description}"

Extract and infer ALL of the following fields. If a field is not explicitly mentioned, infer it creatively and realistically based on the industry, location, and context. Make every field sound authentic and professional — never use "Lorem ipsum" or obviously fake data. For contact info that isn't mentioned, use realistic-sounding placeholders (e.g., "info@miamilawgroup.com", "(305) 555-0190").

Return ONLY valid JSON with EXACTLY this structure (no markdown, no explanation, just the raw JSON object):

{{
  "business_name": "string — infer a professional name if not stated",
  "tagline": "string — memorable, 5–10 words, benefit-driven",
  "industry": "string — one or two words (e.g. 'Immigration Law', 'HVAC Services')",
  "target_audience": "string — who this business serves",
  "color_scheme": {{
    "primary": "string — 6-digit hex, professional, fits the industry",
    "secondary": "string — 6-digit hex, lighter background tone",
    "accent": "string — 6-digit hex, call-to-action color, contrasts well"
  }},
  "services": [
    {{
      "name": "string",
      "description": "string — one sentence"
    }}
  ],
  "about": "string — 2–3 sentences about origin/mission, written in first person plural (We...)",
  "contact": {{
    "email": "string",
    "phone": "string",
    "address": "string"
  }},
  "social_links": {{
    "facebook": "string or null",
    "instagram": "string or null",
    "linkedin": "string or null",
    "twitter": "string or null"
  }}
}}

Rules:
- Infer 3–5 services appropriate for this type of business
- Choose colors that professionals in this industry would actually use (law → navy/gold, tech → blue/teal, food → warm amber, medical → clean blue/white, construction → dark orange/charcoal)
- Primary should be dark enough for white text to be readable on top of it
- Secondary should be a very light neutral (e.g. #f5f7fa, #f0f4f8) suitable as a section background
- Accent should be a warm, action-oriented color (gold, orange, green, coral — never the same as primary)
- Set social_links to null for any platform not mentioned — do not invent social handles
- IMPORTANT: Write all user-facing text in Spanish (Castellano): tagline, about, and every service name and description. Keep industry, color hex values, contact fields, and social_links values in their original form (industry must stay in English for internal processing)."""


def fetch_google_places_data(place_id: str) -> dict | None:
    """Fetch rating, review count, and top 5 reviews from Google Places API."""
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("Warning: GOOGLE_PLACES_API_KEY not set — skipping Google Places enrichment.")
        return None
    if googlemaps is None:
        print("Warning: 'googlemaps' package not installed — skipping Google Places enrichment.")
        return None

    print(f"Fetching Google Places data for place_id: {place_id}")
    gmaps = googlemaps.Client(key=api_key)
    result = gmaps.place(
        place_id,
        fields=["rating", "user_ratings_total", "reviews"],
        language="en",
    )

    place = result.get("result", {})
    if not place:
        print("Warning: No data returned from Google Places API.")
        return None

    raw_reviews = place.get("reviews", [])
    reviews = [
        {
            "author": r.get("author_name", "Anonymous"),
            "rating": r.get("rating", 5),
            "text": r.get("text", ""),
            "relative_time": r.get("relative_time_description", ""),
        }
        for r in raw_reviews[:5]
    ]

    data = {
        "rating": place.get("rating"),
        "review_count": place.get("user_ratings_total"),
        "reviews": reviews,
    }
    print(f"  Google rating : {data['rating']} ({data['review_count']} reviews)")
    print(f"  Reviews fetched: {len(reviews)}")
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Extract structured business info from a plain-text description."
    )
    parser.add_argument("description", nargs="+", help="Plain-text business description")
    parser.add_argument(
        "--place-id",
        metavar="PLACE_ID",
        default=None,
        help="Google Places place_id to fetch real reviews and ratings",
    )
    args = parser.parse_args()
    description = " ".join(args.description)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set. Add it to your .env file:")
        print("  ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f'Extracting business info from: "{description}"')
    print("Calling Claude API...")

    prompt = EXTRACTION_PROMPT.format(description=description)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if the model wrapped the JSON
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

    try:
        business_info = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: LLM returned invalid JSON: {e}")
        print("Raw response:")
        print(raw)
        sys.exit(1)

    # Enrich with Google Places data if a place_id was supplied
    if args.place_id:
        places_data = fetch_google_places_data(args.place_id)
        if places_data:
            business_info["google_places"] = places_data

    Path(".tmp").mkdir(exist_ok=True)
    output_path = Path(".tmp/business_info.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(business_info, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Saved to {output_path}")
    print(f"  Business : {business_info.get('business_name', 'N/A')}")
    print(f"  Industry : {business_info.get('industry', 'N/A')}")
    print(f"  Tagline  : {business_info.get('tagline', 'N/A')}")
    print(f"  Services : {len(business_info.get('services', []))} defined")
    colors = business_info.get("color_scheme", {})
    print(f"  Colors   : primary={colors.get('primary')}  accent={colors.get('accent')}")
    if "google_places" in business_info:
        gp = business_info["google_places"]
        print(f"  Reviews  : {gp.get('rating')} stars, {gp.get('review_count')} reviews")
    print("\nNext step: python tools/generate_copy.py")


if __name__ == "__main__":
    main()
