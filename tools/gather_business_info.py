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

Extract and infer ALL of the following fields. If a field is not explicitly mentioned, infer it creatively and realistically based on the industry, location, and context. Make every field sound authentic and professional — never use "Lorem ipsum" or obviously fake data. For contact info that isn't mentioned, use realistic-sounding placeholders (e.g., "info@bordadosregisol.es", "965 555 190").

Return ONLY valid JSON with EXACTLY this structure (no markdown, no explanation, just the raw JSON object):

{{
  "business_name": "string — infer a professional name if not stated",
  "tagline": "string — memorable, 5–10 words, benefit-driven, unique to this specific business",
  "industry": "string — one or two words (e.g. 'Home Textiles', 'Embroidery', 'Textile Manufacturing')",
  "target_audience": "string — who this business serves",
  "color_scheme": {{
    "primary": "string — 6-digit hex, professional, MUST fit the specific business type (see color rules below)",
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
  }},
  "design_hints": {{
    "font_pairing": "string — one of exactly: Classic, Editorial, Refined, Geometric, Warm",
    "hero_layout": "string — one of exactly: Centered, Left-aligned, Diagonal, Split",
    "visual_personality": "string — one of exactly: Minimal, Bold, Warm, Corporate, Modern",
    "page_layout": "string — one of exactly: Classic, Story-first, Services-focused, Minimal"
  }}
}}

Rules:
- Infer 3–5 services appropriate for this SPECIFIC type of business — avoid generic services
- COLOR DIVERSITY IS CRITICAL. Do NOT default to navy blue or dark purple for all textile businesses. Choose colors based on the specific business type:
  * Home textiles/decoración → warm neutrals, sage greens (#4a6741), dusty pinks (#8b5a5a), warm taupes (#6b5b4e)
  * Embroidery/bordados → rich jewel tones, deep burgundy (#6b2737), forest green (#2d5a3d), royal blue (#2b4570)
  * Fashion/moda → trendy palettes, charcoal black (#2d2d2d), deep teal (#1a535c), plum (#5c2d5a)
  * Industrial finishing/acabados → steel grey (#4a5568), industrial blue (#37587e), slate (#475569)
  * Yarn/hilados → earth tones, terracotta (#8b4513), olive (#5a6342), warm brown (#6b4423)
  * Sewing workshops/confección → warm colors, deep rose (#7a3b4e), indigo (#3b3b7a), chestnut (#6b4226)
  * NEVER use colors in the range #1e3a5f to #2c3e6b or #3d2b4f to #4a2c6e — these are overused
- Primary should be dark enough for white text to be readable on top of it
- Secondary should be a very light neutral (e.g. #f5f7fa, #faf8f5, #f0f4f2) that complements the primary — vary this too
- Accent should be a warm, action-oriented color that contrasts with primary — vary widely (gold, coral, amber, teal, burnt orange, emerald)
- Set social_links to null for any platform not mentioned — do not invent social handles
- IMPORTANT: Write all user-facing text in Spanish (Castellano): tagline, about, and every service name and description. Keep industry, color hex values, contact fields, and social_links values in their original form (industry must stay in English for internal processing).
- Make each tagline unique and specific to this business — avoid generic phrases like "Tu socio textil de confianza".
- DESIGN HINTS — reason from the business identity, not from the name. Pick each value by thinking about who this business is and what feeling its site should communicate:
  * font_pairing: Classic (Playfair, formal/traditional) | Editorial (DM Serif, modern editorial) | Refined (Cormorant, luxury/delicate) | Geometric (Josefin, clean/industrial) | Warm (Bitter, approachable/craft)
    — Examples: bridal/luxury boutique → Refined; industrial supplier/acabados → Geometric; artisanal embroidery/local workshop → Warm; fashion brand → Editorial; established family business → Classic
  * hero_layout: Centered (bold statement, symmetrical) | Left-aligned (text-forward, editorial) | Diagonal (dynamic, fashion-forward) | Split (text left, image right — service + image balance)
    — Examples: single strong brand identity → Centered; boutique/fashion → Diagonal; service business with key visual → Split; copy-led or minimal → Left-aligned
  * visual_personality: Minimal (airy, lots of whitespace) | Bold (strong contrast, thick typography) | Warm (soft textures, human, handcrafted) | Corporate (structured, formal, B2B) | Modern (glass, gradients, contemporary)
    — Examples: artisan seamstress → Warm; yarn/hilados supplier → Warm or Bold; industrial textile finishing → Corporate; fashion boutique → Modern or Bold; home textiles → Warm or Minimal
  * page_layout: Classic (hero→trust→services→reviews→about) | Story-first (hero→about→services→faq) | Services-focused (hero→services→stats→reviews) | Minimal (hero→about→services→contact only)
    — Examples: business with rich history → Story-first; technical/B2B supplier → Services-focused or Classic; small one-person workshop → Minimal; established multi-service business → Classic"""


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
        max_tokens=1800,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    print(f"[TOKENS] input={message.usage.input_tokens} output={message.usage.output_tokens}")

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

    # Merge classification data from batch_build if available
    cls_path = Path(".tmp/business_classification.json")
    if cls_path.exists():
        try:
            with open(cls_path, encoding="utf-8") as f:
                classification = json.load(f)
            business_info["business_type"] = classification
            print(f"  Merged classification: {classification.get('specialty')} / {classification.get('customer_focus')}")
        except (json.JSONDecodeError, IOError):
            pass

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
    dh = business_info.get("design_hints", {})
    if dh:
        print(f"  Design   : font={dh.get('font_pairing')} | hero={dh.get('hero_layout')} | style={dh.get('visual_personality')} | layout={dh.get('page_layout')}")
    if "google_places" in business_info:
        gp = business_info["google_places"]
        print(f"  Reviews  : {gp.get('rating')} stars, {gp.get('review_count')} reviews")
    print("\nNext step: python tools/generate_copy.py")


if __name__ == "__main__":
    main()
