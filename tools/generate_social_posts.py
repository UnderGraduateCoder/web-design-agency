import sys
import os
import json
import re
import argparse
import subprocess
from datetime import date
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

sys.path.insert(0, str(Path(__file__).parent))
import db

PLATFORMS = ["instagram", "linkedin", "facebook"]
POSTS_PER_PLATFORM = 4
TOTAL_POSTS = PLATFORMS.__len__() * POSTS_PER_PLATFORM  # 12


def _iso_week_str(d: date) -> str:
    """Return ISO week string, e.g. '2026-W16'."""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _extract_website_content(slug: str) -> dict:
    """Parse index.html for business name, services, tagline, testimonials, primary color."""
    index_path = Path("output/websites") / slug / "index.html"
    if not index_path.exists():
        return {}

    html = index_path.read_text(encoding="utf-8")

    # Business name from <title>
    title_m = re.search(r'<title>([^<|]+)', html)
    business_name = title_m.group(1).strip() if title_m else ""

    # Tagline: first <p> after the first <h1>
    h1_m = re.search(r'<h1[^>]*>.*?</h1>(.*?)<p[^>]*>(.*?)</p>', html, re.DOTALL)
    tagline = re.sub(r'<[^>]+>', '', h1_m.group(2)).strip() if h1_m else ""

    # Services: h3 text inside service/feature cards
    service_h3s = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL)
    services = [re.sub(r'<[^>]+>', '', s).strip() for s in service_h3s[:6] if s.strip()]

    # Testimonials: blockquote or review text
    bq = re.findall(r'<blockquote[^>]*>(.*?)</blockquote>', html, re.DOTALL)
    testimonials = [re.sub(r'<[^>]+>', '', t).strip()[:180] for t in bq[:3] if t.strip()]

    # Primary color from :root
    root_m = re.search(r':root\s*\{([^}]+)\}', html, re.DOTALL)
    primary_color = "#C17A3A"  # WAT default
    if root_m:
        for pat in [r'--primary\s*:\s*(#[0-9a-fA-F]{6})', r'--copper\s*:\s*(#[0-9a-fA-F]{6})']:
            cm = re.search(pat, root_m.group(1))
            if cm:
                primary_color = cm.group(1)
                break

    return {
        "business_name": business_name,
        "tagline": tagline,
        "services": services,
        "testimonials": testimonials,
        "primary_color": primary_color,
    }


def _generate_captions(client: dict, web_content: dict) -> list[dict]:
    """Call Claude to generate 12 social media captions. Returns list of post dicts."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client_obj = anthropic.Anthropic(api_key=api_key)

    business_name = web_content.get("business_name") or client.get("business_name", "")
    sector = client.get("sector") or "negocio local"
    tagline = web_content.get("tagline", "")
    services = web_content.get("services", [])
    testimonials = web_content.get("testimonials", [])
    primary_color = web_content.get("primary_color", "#C17A3A")

    services_str = "\n".join(f"- {s}" for s in services) if services else "- (no disponible)"
    testimonials_str = "\n".join(f'- "{t}"' for t in testimonials) if testimonials else "- (no disponible)"

    system_prompt = """Eres un especialista en marketing de contenidos para negocios locales. Generas packs de redes sociales semanales en español.

REGLAS POR PLATAFORMA:
- Instagram (4 posts): 150–220 caracteres, máximo 2 emojis, terminar con bloque de hashtags (8–12 etiquetas relevantes), storytelling visual
- LinkedIn (4 posts): 300–500 caracteres, tono profesional, máximo 3 hashtags al final, comenzar con un insight o dato útil, CTA a visitar web o llamar
- Facebook (4 posts): 100–200 caracteres, tono cercano y conversacional, una pregunta para fomentar comentarios, CTA directo ("Llámanos", "Visítanos")

REGLAS GENERALES:
- Idioma: español
- Prohibidas: "innovador", "robusto", "transformador", "sinergia", "solución innovadora", "empoderamos", "vanguardia"
- Cada post debe tener un tema diferente (no repetir el mismo mensaje)
- Contenido basado ÚNICAMENTE en los datos del negocio proporcionados — no inventar servicios, precios ni estadísticas
- Variedad de temas: presentación del servicio, testimonio/caso de éxito, consejo útil del sector, CTA directo

FORMATO DE RESPUESTA — JSON array puro, sin markdown:
[
  { "platform": "instagram", "index": 1, "theme": "...", "caption": "...", "hashtags": "#tag1 #tag2 ..." },
  ...
]
Para LinkedIn y Facebook, "hashtags" puede ser "" o máximo 3 tags al final del caption."""

    user_prompt = f"""Negocio: {business_name}
Sector: {sector}
Tagline: {tagline}

Servicios:
{services_str}

Testimonios:
{testimonials_str}

Genera 12 posts: 4 Instagram + 4 LinkedIn + 4 Facebook."""

    print(f"  Generating 12 captions via Claude...")
    message = client_obj.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r'^```(?:json)?\n?', '', raw)
    raw = re.sub(r'\n?```$', '', raw)

    try:
        posts = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: Claude returned invalid JSON: {e}\nRaw: {raw[:400]}")
        sys.exit(1)

    # Enforce LinkedIn hashtag limit
    for p in posts:
        if p.get("platform") == "linkedin" and p.get("hashtags"):
            tags = p["hashtags"].split()[:3]
            p["hashtags"] = " ".join(tags)

    return posts


def _build_kie_prompt_social(theme: str, sector: str, primary_color: str, index: int) -> dict:
    """Build Dense Narrative JSON for a 1:1 Instagram image."""
    return {
        "prompt": (
            f"Minimal editorial flat-lay photograph for Instagram representing theme: {theme}. "
            f"Sector: {sector}. Brand accent colour: {primary_color}. "
            "Clean white or neutral background with single hero object. "
            "Shot on 85mm lens, f/2.8, ISO 100, soft diffused studio light from left. "
            "Modern, premium, no text overlay, no people. Do not beautify. No CGI. No stock photo aesthetic."
        ),
        "negative_prompt": "blurry, text, watermark, people, CGI, oversaturated, stock photo, cluttered, busy background",
        "settings": {
            "style": "editorial product photography, minimal",
            "lighting": "soft studio, diffused from left",
            "camera_angle": "overhead or 45-degree, 85mm",
            "depth_of_field": "moderate, f/2.8",
            "quality": "high detail",
        },
        "api_parameters": {
            "aspect_ratio": "1:1",
            "resolution": "1K",
            "output_format": "jpg",
        },
    }


def _generate_instagram_images(slug: str, ig_posts: list[dict], sector: str, primary_color: str, week_dir: Path) -> list[str]:
    """Generate 4 Instagram images. Returns list of image paths/URLs."""
    kie_key = os.getenv("KIE_API_KEY", "")
    prompt_dir = Path("output/prompts") / slug
    prompt_dir.mkdir(parents=True, exist_ok=True)
    week_label = week_dir.name

    image_paths = []
    for post in ig_posts:
        n = post["index"]
        theme = post.get("theme", f"servicio {n}")
        out_img = week_dir / f"instagram-{n}.jpg"

        if not kie_key:
            image_paths.append(f"https://placehold.co/1080x1080")
            continue

        prompt_path = prompt_dir / f"social-{week_label}-ig-{n}.json"
        prompt_data = _build_kie_prompt_social(theme, sector, primary_color, n)
        prompt_path.write_text(json.dumps(prompt_data, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"  Generating Instagram image {n}/4...")
        result = subprocess.run(
            [sys.executable, "tools/scripts/generate_kie.py",
             str(prompt_path), str(out_img), "1:1"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  [WARN] KIE failed for image {n}: {result.stderr.strip()}")
            image_paths.append(f"https://placehold.co/1080x1080")
        else:
            image_paths.append(str(out_img).replace("\\", "/"))

    return image_paths


def _save_captions(posts: list[dict], week_dir: Path) -> None:
    """Save each post's caption + hashtags as a .txt file."""
    for post in posts:
        platform = post["platform"]
        n = post["index"]
        caption = post.get("caption", "")
        hashtags = post.get("hashtags", "")
        content = caption
        if hashtags:
            content = f"{caption}\n\n{hashtags}"
        out_path = week_dir / f"{platform}-{n}.txt"
        out_path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate weekly social media pack for a WAT client")
    parser.add_argument("--client-slug", required=True)
    args = parser.parse_args()

    slug = args.client_slug
    today = date.today()
    week_str = _iso_week_str(today)
    week_num = today.isocalendar()[1]

    print(f"[social-content] Client: {slug} | Week: {week_str}")

    # Step 1 — Validate client
    client = db.get_client(slug)
    if not client:
        print(f"Error: Client '{slug}' not found in database.")
        sys.exit(1)

    sector = client.get("sector") or "negocio local"

    # Step 2 — Extract website content
    web_content = _extract_website_content(slug)
    if not web_content:
        print(f"  [WARN] No website found for {slug} — using DB data only")
        web_content = {
            "business_name": client.get("business_name", slug),
            "tagline": "", "services": [], "testimonials": [],
            "primary_color": "#C17A3A",
        }
    primary_color = web_content.get("primary_color", "#C17A3A")
    print(f"  Business: {web_content.get('business_name')} | Color: {primary_color}")

    # Step 3 — Generate captions
    all_posts = _generate_captions(client, web_content)
    ig_posts = [p for p in all_posts if p["platform"] == "instagram"]
    print(f"  Generated {len(all_posts)} captions")

    # Create output directory
    week_dir = Path("output/social") / slug / week_str
    week_dir.mkdir(parents=True, exist_ok=True)

    # Step 4 — Generate Instagram images
    if not os.getenv("KIE_API_KEY"):
        print("  [WARN] KIE_API_KEY not set — using placehold.co for Instagram images")
    _generate_instagram_images(slug, ig_posts, sector, primary_color, week_dir)

    # Step 5 — Save caption files
    _save_captions(all_posts, week_dir)
    print(f"  Saved {len(all_posts)} caption files to {week_dir}")

    # Verify counts
    txt_files = list(week_dir.glob("*.txt"))
    print(f"  Caption files: {len(txt_files)} (expected 12)")

    # Step 6 — Log to DB
    row_id = db.log_social_generation(
        slug,
        week_of_year=week_num,
        post_count=len(all_posts),
        output_path=str(week_dir).replace("\\", "/"),
    )
    print(f"  DB row id: {row_id}")
    print(f"[social-content] Done — output at {week_dir}")


if __name__ == "__main__":
    main()
