"""
generate_images.py

Usage:
    python tools/generate_images.py

Reads .tmp/business_info.json, builds an industry-specific prompt, and generates
a hero background image using Gemini image generation (primary) with Stability AI
as a fallback. Saves to output/assets/<slug>_hero.jpg and writes "hero_image_path"
back into business_info.json.

Requires (at least one):
    GEMINI_API_KEY in .env     — Primary. Google AI Studio (free tier available).
    STABILITY_API_KEY in .env  — Fallback. platform.stability.ai (~$0.003/image)
"""

import sys
import json
import os
import re
import base64
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
# Industry → prompt mapping
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert business name to a safe, lowercase filename slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)      # remove non-alphanumeric except hyphens/spaces
    text = re.sub(r"[\s_]+", "-", text)        # spaces/underscores → hyphens
    text = re.sub(r"-{2,}", "-", text)         # collapse multiple hyphens
    return text.strip("-") or "business"


INDUSTRY_PROMPTS = {
    "immigration law": "modern law firm lobby, polished marble floors, warm professional lighting, American flag in background, wide angle architectural photography",
    "law": "elegant law firm interior, dark wood bookshelves, conference table, dramatic lighting, photorealistic wide angle",
    "hvac": "professional HVAC technician tools neatly arranged, modern ductwork, clean industrial aesthetic, cool blue tones",
    "plumbing": "pristine plumbing fixtures and copper pipes, clean workshop, warm lighting, professional trade aesthetic",
    "electrical": "modern electrical panel and clean wiring, professional workshop, industrial chic, cool grey tones",
    "construction": "professional construction site at golden hour, steel framework, dramatic sky, wide angle",
    "roofing": "aerial view of residential neighborhood, clean rooftops, blue sky with light clouds, professional real estate photography",
    "landscaping": "beautifully manicured garden with lush greenery, vibrant flowers, professional landscape design, golden hour lighting",
    "cleaning": "spotless modern interior with sunlight streaming through windows, pristine surfaces, crisp and clean aesthetic",
    "medical": "modern medical clinic reception area, clean white interior, soft professional lighting, calming atmosphere",
    "dental": "bright modern dental office, clean minimalist design, professional dental chair, calming blue and white tones",
    "restaurant": "upscale restaurant interior, warm candlelight, elegant table settings, dark wood and soft ambient lighting",
    "cafe": "cozy coffee shop with exposed brick, hanging Edison bulbs, wooden tables, latte art close-up",
    "bakery": "artisan bakery with freshly baked bread on wooden shelves, warm golden lighting, rustic aesthetic",
    "fitness": "modern gym interior, gleaming equipment, motivational lighting, wide angle architectural photography",
    "yoga": "serene yoga studio with natural light, wooden floors, green plants, minimalist zen aesthetic",
    "beauty": "modern beauty salon interior, elegant decor, pastel tones, professional styling chairs, bright natural light",
    "real estate": "stunning luxury home exterior at twilight, warm interior lights glowing, manicured front lawn, wide angle",
    "photography": "professional photography studio with large softboxes, clean white backdrop, camera equipment arranged artistically",
    "accounting": "modern professional office with city view, clean desk setup, business documents, blue and white tones",
    "consulting": "executive boardroom with panoramic city view, sleek conference table, professional business atmosphere",
    "tech": "modern tech startup office, open plan with exposed ceiling, multiple monitors, clean minimalist design",
    "software": "abstract digital network visualization, blue glowing nodes and connections, dark background, futuristic aesthetic",
    "marketing": "creative agency office with colorful branding elements, modern open workspace, vibrant and energetic atmosphere",
    "education": "modern classroom or library with natural light, rows of books, inspiring learning environment",
    "tutoring": "bright study room with books and learning materials, warm lighting, focused and inviting atmosphere",
    "childcare": "bright cheerful daycare interior with colorful educational toys, safe clean environment, warm natural light",
    "pet": "modern veterinary clinic or pet grooming salon, clean bright interior, happy pet-friendly atmosphere",
    "automotive": "modern auto repair shop with gleaming tools, professional lighting, clean workshop aesthetic",
    "logistics": "professional warehouse or logistics hub, organized shelving, modern industrial lighting",
    "security": "modern security operations center with multiple screens, professional monitoring environment, blue tones",
    "insurance": "professional office building exterior, clean corporate architecture, blue sky, trust-inspiring aesthetic",
    "financial": "elegant financial advisory office, dark wood and leather, city skyline view, professional and trustworthy",
    "textile": "modern textile factory with colorful fabric rolls stacked on shelves, professional industrial photography, warm lighting, wide angle",
    "manufacturing": "modern textile factory with colorful fabric rolls stacked on shelves, professional industrial photography, warm lighting, wide angle",
    "fabric": "modern textile factory with colorful fabric rolls stacked on shelves, professional industrial photography, warm lighting, wide angle",
    "clothing": "modern garment manufacturing facility, fabric rolls and sewing machines, professional industrial lighting, wide angle",
    "confecciones": "modern garment manufacturing facility, fabric rolls and sewing machines, professional industrial lighting, wide angle",
    "tejidos": "modern textile factory with colorful fabric rolls stacked on shelves, professional industrial photography, warm lighting, wide angle",
    "garment": "modern garment manufacturing facility, fabric rolls and sewing machines, professional industrial lighting, wide angle",
}

DEFAULT_PROMPT = "professional business office interior, modern clean design, natural light, wide angle architectural photography"


def get_industry_prompt(industry: str) -> str:
    """Match industry string to a prompt template."""
    industry_lower = industry.lower()
    for key, prompt in INDUSTRY_PROMPTS.items():
        if key in industry_lower or industry_lower in key:
            return prompt
    return DEFAULT_PROMPT


# ---------------------------------------------------------------------------
# Gemini image generation (primary)
# ---------------------------------------------------------------------------

def generate_hero_image_gemini(prompt: str, output_path: Path) -> bool:
    """Call Gemini image generation API and save the result. Returns True on success.
    Note: Gemini image model names change frequently. On 404, falls back to Stability AI immediately.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("  GEMINI_API_KEY not set — falling back to Stability AI.")
        return False

    # Try known model names in order. On 404, move to the next one.
    GEMINI_MODELS = [
        "gemini-2.0-flash-preview-image-generation",
        "gemini-2.0-flash-exp-image-generation",
    ]
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }

    print("Calling Gemini image generation (primary)...")
    print(f"  Prompt: {prompt[:80]}...")

    resp = None
    for model in GEMINI_MODELS:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
        except requests.Timeout:
            print("  Warning: Gemini request timed out — falling back to Stability AI.")
            return False
        except requests.RequestException as e:
            print(f"  Warning: Gemini request failed: {e} — falling back to Stability AI.")
            return False
        if resp.status_code != 404:
            break
        print(f"  Model {model} not available (404), trying next...")

    if resp is None or resp.status_code != 200:
        code = resp.status_code if resp else "N/A"
        print(f"  Warning: Gemini returned HTTP {code} — falling back to Stability AI.")
        try:
            print(f"  Detail: {resp.json()}")
        except Exception:
            pass
        return False

    try:
        data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        image_part = next(p for p in parts if "inlineData" in p)
        image_bytes = base64.b64decode(image_part["inlineData"]["data"])
    except (KeyError, IndexError, StopIteration, Exception) as e:
        print(f"  Warning: Could not parse Gemini response: {e} — falling back to Stability AI.")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(image_bytes)

    size_kb = len(image_bytes) / 1024
    print(f"  Image saved: {output_path} ({size_kb:.0f} KB)")
    return True


# ---------------------------------------------------------------------------
# Stability AI (fallback)
# ---------------------------------------------------------------------------

def generate_hero_image_stability(prompt: str, negative_prompt: str, output_path: Path) -> bool:
    """Call Stability AI Stable Image Core and save the result. Returns True on success."""
    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        print("  STABILITY_API_KEY not set — no fallback available.")
        return False

    url = "https://api.stability.ai/v2beta/stable-image/generate/core"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "image/*",
    }
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "aspect_ratio": "16:9",
        "output_format": "jpeg",
    }

    print("Calling Stability AI (fallback)...")
    print(f"  Prompt: {prompt[:80]}...")

    try:
        resp = requests.post(url, headers=headers, files={"none": ""}, data=payload, timeout=30)
    except requests.Timeout:
        print("  Warning: Stability AI request timed out after 30s.")
        return False
    except requests.RequestException as e:
        print(f"  Warning: Stability AI request failed: {e}")
        return False

    if resp.status_code != 200:
        print(f"  Error: Stability AI returned HTTP {resp.status_code}")
        try:
            print(f"  Detail: {resp.json()}")
        except Exception:
            print(f"  Body: {resp.text[:200]}")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(resp.content)

    size_kb = len(resp.content) / 1024
    print(f"  Image saved: {output_path} ({size_kb:.0f} KB)")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    info_path = Path(".tmp/business_info.json")
    if not info_path.exists():
        print("Error: .tmp/business_info.json not found.")
        print("Run gather_business_info.py first.")
        sys.exit(1)

    with open(info_path, encoding="utf-8") as f:
        business_info = json.load(f)

    industry = business_info.get("industry", "business")
    business_name = business_info.get("business_name", "")
    primary_color = (
        business_info.get("brand", {}).get("primary_color")
        or business_info.get("color_scheme", {}).get("primary", "")
    )

    base_prompt = get_industry_prompt(industry)
    # Optionally weave in the brand's primary color tone
    color_hint = f", {primary_color} color accent" if primary_color else ""
    full_prompt = f"{base_prompt}{color_hint}, no text, no people, no watermarks, photorealistic, 4K"
    negative_prompt = "text, watermarks, logos, people, faces, cartoonish, illustration, low quality, blurry, ugly"

    slug = slugify(business_name) if business_name else "business"
    image_filename = f"{slug}_hero.jpg"
    output_path = Path(f"output/assets/{image_filename}")

    # Try Gemini first; fall back to Stability AI
    success = generate_hero_image_gemini(full_prompt, output_path)
    if not success:
        success = generate_hero_image_stability(full_prompt, negative_prompt, output_path)

    if not success:
        print("\nSkipping hero image — pipeline continues without it.")
        sys.exit(0)

    # Write the path back into business_info.json (only on success)
    business_info["hero_image_path"] = f"assets/{image_filename}"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(business_info, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] business_info.json updated with hero_image_path")
    print(f"  Industry detected : {industry}")
    print(f"  Image path        : output/assets/{image_filename}")
    print("\nNext step: python tools/generate_copy.py")


if __name__ == "__main__":
    main()
