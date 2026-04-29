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
import argparse
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
{specialty_context}
Write complete website copy for each section below. Make it feel like this business has a real personality and genuine expertise. Vary sentence length. Use active voice. Be direct. Make the copy UNIQUE to this specific business — avoid generic phrases that could apply to any company.

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
Generate {faq_count} FAQ items — real questions this audience asks before hiring. Answers must be direct and build trust.
{cta_style_instruction}
Do not invent fake testimonials or quotes unless real reviews were provided above.{testimonials_instruction}"""


# Pass 1: hero + SEO only — establishes design language before committing to full site
HERO_ONLY_PROMPT = """IMPORTANT: Write ALL copy in Spanish (Castellano) — every string in the output JSON.

You are a senior conversion copywriter. Write a hero headline and SEO metadata for a real business. Your writing is confident, customer-focused, benefit-driven, and unique to this specific business. No corporate jargon, no generic phrases.

Business Details:
- Name: {business_name}
- Tagline: {tagline}
- Industry: {industry}
- Target Audience: {target_audience}
- About: {about}
- Services:
{services_list}
{specialty_context}
The hero headline is the most important line on the entire website. Make it bold, specific, and immediately communicate the core value this business delivers. Do not start with 'We'. Do not use vague words like 'solutions', 'excellence', or 'quality'.

Return ONLY valid JSON with EXACTLY this structure (no markdown, no explanation):

{{
  "hero": {{
    "headline": "string — bold, benefit-driven, max 10 words. Must be specific to this business.",
    "subheadline": "string — 1–2 sentences expanding on the headline, speaks to the audience's real pain point or desire",
    "cta_primary": "string — action button text, 2–4 words",
    "cta_secondary": "string — softer secondary CTA, 2–4 words"
  }},
  "seo": {{
    "title": "string — page title tag, 50–60 chars, format: '{{business_name}} | {{primary service}} en {{city}}' if location known",
    "meta_description": "string — 140–160 chars, benefit-driven, includes a soft CTA"
  }}
}}

{cta_style_instruction}"""


# Pass 2: all sections except hero — hero is locked and provided as context
SECTIONS_PROMPT = """IMPORTANT: Write ALL copy in Spanish (Castellano) — every string in the output JSON: section titles, paragraphs, stat labels, FAQ answers, and the footer tagline.

You are a senior conversion copywriter. The hero section is ALREADY APPROVED — do not modify it. Your task is to write the remaining sections so they feel like a natural, coherent continuation of the hero's voice and personality.

Business Details:
- Name: {business_name}
- Tagline: {tagline}
- Industry: {industry}
- Target Audience: {target_audience}
- About: {about}
- Services:
{services_list}
{reviews_context}
{specialty_context}
APPROVED HERO (maintain this exact voice and personality throughout):
{approved_hero_json}

Write complete copy for the remaining sections below. Keep the same personality established by the hero. Vary sentence length. Use active voice. Be direct. Make every section UNIQUE to this specific business.

Return ONLY valid JSON with EXACTLY this structure (no markdown, no explanation):

{{
  "about": {{
    "section_title": "string — 2–4 words for the section label",
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
    "section_title": "string — 3–5 words",
    "statement": "string — 1–2 sentences of authority-building (experience, track record, client outcomes)",
    "stats": [
      {{"number": "string — impressive but credible number", "label": "string — what it measures"}},
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
    "tagline": "string — short, memorable brand closing line (different from the hero headline)"
  }},
  "faq": [
    {{
      "question": "string — a real question {target_audience} asks before hiring a {industry} business",
      "answer": "string — 2–4 sentences, direct and reassuring, builds trust"
    }}
  ]{testimonials_schema}
}}

Generate a service copy entry for each of these {service_count} services: {service_names}.
Stats should be realistic and appropriate for a {industry} business.
Generate {faq_count} FAQ items — real questions this audience asks before hiring. Answers must be direct and build trust.
{cta_style_instruction}
Do not invent fake testimonials or quotes unless real reviews were provided above.{testimonials_instruction}"""


def _load_business_context(business_info: dict) -> dict:
    """Extract shared context fields used by all prompt variants."""
    import hashlib
    services = business_info.get("services", [])
    services_list = "\n".join(
        f"  - {s['name']}: {s.get('description', '')}" for s in services
    )
    service_names = ", ".join(s["name"] for s in services)

    specialty_context = ""
    cta_style_instruction = ""
    faq_count = "5-7"
    cls_path = Path(".tmp/business_classification.json")
    if cls_path.exists():
        try:
            with open(cls_path, encoding="utf-8") as f:
                cls = json.load(f)
            specialty = cls.get("specialty", "")
            customer = cls.get("customer_focus", "")
            specialty_hints = {
                "embroidery": "This is an embroidery specialist. Emphasize precision, custom designs, industrial capacity, and artisan techniques. Use vocabulary related to thread, needlework, and decoration.",
                "home_textiles": "This is a home textiles company. Emphasize comfort, quality fabrics, interior design, and creating warm living spaces. Use vocabulary about home, comfort, and materials.",
                "sewing_workshop": "This is a sewing/confection workshop. Emphasize craftsmanship, pattern-making, tailoring, attention to detail, and custom work.",
                "yarn_spinning": "This is a yarn/fiber company. Emphasize raw materials quality, fiber sourcing, spinning techniques, and supply chain reliability.",
                "textile_finishing": "This is a textile finishing company. Emphasize technical processes, quality control, surface treatments, and industrial innovation.",
                "fashion_retail": "This is a fashion/retail business. Emphasize trends, personal style, curated collections, and the shopping experience.",
                "sample_making": "This is a textile sample-making workshop. Emphasize speed, accuracy, prototyping, and close collaboration with designers.",
            }
            specialty_context = specialty_hints.get(specialty, "")
            cta_map = {
                "b2b": "CTA buttons should use B2B language: 'Solicita Presupuesto', 'Pide Muestras', 'Contacta con Ventas'. Tone should be professional and results-oriented.",
                "b2c": "CTA buttons should use consumer language: 'Descubre Nuestra Coleccion', 'Visita la Tienda', 'Pide Tu Presupuesto'. Tone should be warm and inviting.",
                "mixed": "CTA buttons should balance professional and approachable: 'Hablemos de Tu Proyecto', 'Consulta Sin Compromiso', 'Pide Informacion'.",
            }
            cta_style_instruction = cta_map.get(customer, "")
            seed = int(hashlib.md5(business_info.get("business_name", "").encode("utf-8")).hexdigest(), 16)
            layout_id = (seed // 5) % 4
            faq_count = "3-4" if layout_id == 3 else "5-7"
        except (json.JSONDecodeError, IOError):
            pass

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

    return {
        "business_name": business_info.get("business_name", ""),
        "tagline": business_info.get("tagline", ""),
        "industry": business_info.get("industry", ""),
        "target_audience": business_info.get("target_audience", ""),
        "about": business_info.get("about", ""),
        "services_list": services_list,
        "services": services,
        "service_count": len(services),
        "service_names": service_names,
        "reviews_context": reviews_context,
        "testimonials_schema": testimonials_schema,
        "testimonials_instruction": testimonials_instruction,
        "specialty_context": specialty_context,
        "cta_style_instruction": cta_style_instruction,
        "faq_count": faq_count,
    }


def _call_claude(client, prompt: str, max_tokens: int) -> dict:
    """Call Claude and parse JSON response."""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    print(f"[TOKENS] input={message.usage.input_tokens} output={message.usage.output_tokens}")
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: LLM returned invalid JSON: {e}")
        print("Raw response:")
        print(raw)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Generate website copy")
    parser.add_argument(
        "--pass", dest="build_pass", type=int, default=None,
        choices=[1, 2],
        help="Pass 1: hero+SEO only. Pass 2: all other sections (reads hero from pass 1). Omit for legacy full single-pass.",
    )
    args = parser.parse_args()

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

    ctx = _load_business_context(business_info)
    client = anthropic.Anthropic(api_key=api_key)
    Path(".tmp").mkdir(exist_ok=True)
    output_path = Path(".tmp/website_copy.json")

    # -------------------------------------------------------------------------
    # Pass 1: hero + SEO only
    # -------------------------------------------------------------------------
    if args.build_pass == 1:
        print(f"[PASS 1] Generating hero + SEO for: {ctx['business_name']}")
        prompt = HERO_ONLY_PROMPT.format(
            business_name=ctx["business_name"],
            tagline=ctx["tagline"],
            industry=ctx["industry"],
            target_audience=ctx["target_audience"],
            about=ctx["about"],
            services_list=ctx["services_list"],
            specialty_context=ctx["specialty_context"],
            cta_style_instruction=ctx["cta_style_instruction"],
        )
        result = _call_claude(client, prompt, max_tokens=800)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Pass 1 saved to {output_path}")
        print(f"  Hero headline: \"{result.get('hero', {}).get('headline', 'N/A')}\"")
        print(f"  SEO title    : \"{result.get('seo', {}).get('title', 'N/A')}\"")
        print("\nNext step: python tools/build_website.py --preview")
        return

    # -------------------------------------------------------------------------
    # Pass 2: all sections except hero, hero locked from pass 1
    # -------------------------------------------------------------------------
    if args.build_pass == 2:
        if not output_path.exists():
            print("Error: .tmp/website_copy.json not found — run --pass 1 first.")
            sys.exit(1)
        with open(output_path, encoding="utf-8") as f:
            existing = json.load(f)
        if "hero" not in existing:
            print("Error: pass 1 hero not found in website_copy.json — run --pass 1 first.")
            sys.exit(1)

        approved_hero_json = json.dumps(existing["hero"], ensure_ascii=False, indent=2)
        print(f"[PASS 2] Generating remaining sections for: {ctx['business_name']}")
        prompt = SECTIONS_PROMPT.format(
            business_name=ctx["business_name"],
            tagline=ctx["tagline"],
            industry=ctx["industry"],
            target_audience=ctx["target_audience"],
            about=ctx["about"],
            services_list=ctx["services_list"],
            service_count=ctx["service_count"],
            service_names=ctx["service_names"],
            reviews_context=ctx["reviews_context"],
            testimonials_schema=ctx["testimonials_schema"],
            testimonials_instruction=ctx["testimonials_instruction"],
            specialty_context=ctx["specialty_context"],
            cta_style_instruction=ctx["cta_style_instruction"],
            faq_count=ctx["faq_count"],
            approved_hero_json=approved_hero_json,
        )
        sections = _call_claude(client, prompt, max_tokens=2700)
        # Merge: hero + seo from pass 1 are authoritative; pass 2 adds all other sections
        merged = {"hero": existing["hero"], "seo": existing.get("seo", {})}
        merged.update({k: v for k, v in sections.items() if k not in ("hero", "seo")})
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        website_copy = merged
        print(f"\n[OK] Pass 2 merged into {output_path}")
        print(f"  Hero         : \"{website_copy.get('hero', {}).get('headline', 'N/A')}\" (from pass 1 — locked)")
        print(f"  Services     : {len(website_copy.get('services', []))} sections written")
        print(f"  Stats        : {len(website_copy.get('social_proof', {}).get('stats', []))} data points")
        print(f"  FAQ          : {len(website_copy.get('faq', []))} Q&As")
        if website_copy.get("testimonials"):
            print(f"  Testimonials : {len(website_copy['testimonials'])} synthesized from real reviews")
        print("\nNext step: python tools/build_website.py")
        return

    # -------------------------------------------------------------------------
    # Legacy: full single-pass (no --pass flag)
    # -------------------------------------------------------------------------
    prompt = COPY_PROMPT.format(
        business_name=ctx["business_name"],
        tagline=ctx["tagline"],
        industry=ctx["industry"],
        target_audience=ctx["target_audience"],
        about=ctx["about"],
        services_list=ctx["services_list"],
        service_count=ctx["service_count"],
        service_names=ctx["service_names"],
        reviews_context=ctx["reviews_context"],
        testimonials_schema=ctx["testimonials_schema"],
        testimonials_instruction=ctx["testimonials_instruction"],
        specialty_context=ctx["specialty_context"],
        cta_style_instruction=ctx["cta_style_instruction"],
        faq_count=ctx["faq_count"],
    )

    print(f"Generating copy for: {ctx['business_name']}")
    print("Calling Claude API...")

    website_copy = _call_claude(client, prompt, max_tokens=3500)
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
