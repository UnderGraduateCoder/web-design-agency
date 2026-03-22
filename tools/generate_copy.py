"""
generate_copy.py

Usage:
    python tools/generate_copy.py

Reads .tmp/business_info.json, calls Claude API to generate professional,
conversion-focused website copy, and writes .tmp/website_copy.json.

Run gather_business_info.py first.
"""

import sys
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import anthropic
except ImportError:
    print("Error: 'anthropic' package not installed. Run: pip install -r requirements.txt")
    sys.exit(1)


COPY_PROMPT = """IMPORTANT: Write ALL copy in Spanish (Castellano) — every string in the output JSON: headlines, subheadlines, CTA button text, section titles, paragraphs, stat labels, FAQ answers, and the footer tagline.

You are a senior conversion copywriter. Your job is to write professional, high-converting website copy for a real business. Your writing is confident, customer-focused, and free of corporate jargon or buzzwords. You write about benefits, not features. You create trust through specificity, not vague claims.

Business Details:
- Name: {business_name}
- Tagline: {tagline}
- Industry: {industry}
- Target Audience: {target_audience}
- About: {about}
- Services:
{services_list}
{reviews_context}
Write complete website copy for each section below. Make it feel like this business has a real personality and genuine expertise. Vary sentence length. Use active voice. Be direct.

Return ONLY valid JSON with EXACTLY this structure (no markdown, no explanation):

{{
  "hero": {{
    "headline": "string — bold, benefit-driven, max 10 words. Do not start with 'We'",
    "subheadline": "string — 1–2 sentences expanding on the headline, speaks to the audience's real pain point or desire",
    "cta_primary": "string — action button text, 2–4 words (e.g. 'Get a Free Consultation')",
    "cta_secondary": "string — softer secondary CTA, 2–4 words (e.g. 'See Our Work')"
  }},
  "about": {{
    "section_title": "string — 2–4 words for the section label (e.g. 'Our Story', 'Who We Are')",
    "paragraphs": [
      "string — paragraph 1: origin story or founding mission",
      "string — paragraph 2: what makes them different / their approach",
      "string — paragraph 3: the promise to the customer"
    ]
  }},
  "services": [
    {{
      "name": "string — service name (match the names from business details exactly)",
      "headline": "string — punchy benefit headline for this service, max 6 words",
      "description": "string — 2 sentences, benefit-focused, no jargon"
    }}
  ],
  "social_proof": {{
    "section_title": "string — 3–5 words (e.g. 'Results That Speak for Themselves')",
    "statement": "string — 1–2 sentences of authority-building (experience, track record, client outcomes)",
    "stats": [
      {{"number": "string — impressive but credible number (e.g. '500+', '98%', '12 Years')", "label": "string — what it measures"}},
      {{"number": "string", "label": "string"}},
      {{"number": "string", "label": "string"}}
    ]
  }},
  "cta_section": {{
    "headline": "string — invitation to act, creates mild urgency, max 10 words",
    "subtext": "string — 1 sentence that removes risk or adds reassurance",
    "button_text": "string — 2–4 words"
  }},
  "footer": {{
    "tagline": "string — short, memorable brand closing line (not the same as the hero tagline)"
  }},
  "faq": [
    {{
      "question": "string — a real question {target_audience} asks before hiring a {industry} business",
      "answer": "string — 2–4 sentences, direct and reassuring, builds trust, no jargon"
    }}
  ],
  "seo": {{
    "title": "string — page title tag, 50–60 chars, format: '{{business_name}} | {{primary service}} en {{city}}' if location known, else '{{business_name}} | {{primary service}}'",
    "meta_description": "string — 140–160 chars, benefit-driven, mention location if known, includes a soft CTA"
  }}{testimonials_schema}
}}

Generate a service copy entry for each of these {service_count} services: {service_names}.
Stats should be realistic and appropriate for a {industry} business.
Generate 5–7 FAQ items — real questions this audience asks before hiring. Answers must be direct and build trust.
Do not invent fake testimonials or quotes unless real reviews were provided above.{testimonials_instruction}"""


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set. Add it to your .env file.")
        sys.exit(1)

    info_path = Path(".tmp/business_info.json")
    if not info_path.exists():
        print("Error: .tmp/business_info.json not found.")
        print("Run Step 1 first: python tools/gather_business_info.py \"your description\"")
        sys.exit(1)

    with open(info_path, encoding="utf-8") as f:
        business_info = json.load(f)

    services = business_info.get("services", [])
    services_list = "\n".join(
        f"  - {s['name']}: {s.get('description', '')}" for s in services
    )
    service_names = ", ".join(s["name"] for s in services)

    # Build optional reviews context block for testimonial synthesis
    reviews_context = ""
    testimonials_schema = ""
    testimonials_instruction = ""
    google_places = business_info.get("google_places", {})
    if google_places.get("reviews"):
        reviews_context = "\nReal Google Reviews (synthesize 2–3 into testimonials — paraphrase, never copy verbatim):\n"
        for r in google_places["reviews"][:5]:
            text = r.get("text", "")
            if text and len(text) > 20:
                author = r.get("author_name", "Cliente")
                rating = r.get("rating", 5)
                reviews_context += f'- {author} ({rating}★): "{text[:200]}"\n'
        testimonials_schema = """,
  "testimonials": [
    {{
      "quote": "string — paraphrased from a real review above, 1–2 sentences, first person",
      "author": "string — first name only from the real review",
      "role": "string — short descriptor like 'Cliente satisfecho' or context-inferred role"
    }}
  ]"""
        testimonials_instruction = "\nIf real reviews were provided, include 2–3 testimonials in the 'testimonials' array — paraphrase them, never copy word for word."

    prompt = COPY_PROMPT.format(
        business_name=business_info.get("business_name", ""),
        tagline=business_info.get("tagline", ""),
        industry=business_info.get("industry", ""),
        target_audience=business_info.get("target_audience", ""),
        about=business_info.get("about", ""),
        services_list=services_list,
        service_count=len(services),
        service_names=service_names,
        reviews_context=reviews_context,
        testimonials_schema=testimonials_schema,
        testimonials_instruction=testimonials_instruction,
    )

    client = anthropic.Anthropic(api_key=api_key)

    print(f"Generating copy for: {business_info.get('business_name')}")
    print("Calling Claude API...")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

    try:
        website_copy = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: LLM returned invalid JSON: {e}")
        print("Raw response:")
        print(raw)
        sys.exit(1)

    Path(".tmp").mkdir(exist_ok=True)
    output_path = Path(".tmp/website_copy.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(website_copy, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Saved to {output_path}")
    print(f"  Hero         : \"{website_copy.get('hero', {}).get('headline', 'N/A')}\"")
    print(f"  Services     : {len(website_copy.get('services', []))} sections written")
    print(f"  Stats        : {len(website_copy.get('social_proof', {}).get('stats', []))} data points")
    print(f"  FAQ          : {len(website_copy.get('faq', []))} Q&As")
    print(f"  SEO title    : \"{website_copy.get('seo', {}).get('title', 'N/A')}\"")
    if website_copy.get("testimonials"):
        print(f"  Testimonials : {len(website_copy['testimonials'])} synthesized from real reviews")
    print("\nNext step: python tools/build_website.py")


if __name__ == "__main__":
    main()
