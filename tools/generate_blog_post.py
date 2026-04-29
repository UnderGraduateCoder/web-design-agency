import sys
import os
import json
import re
import argparse
import subprocess
import html as html_lib
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

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

BANNED_WORDS = [
    "delve", "tapestry", "leverage", "innovative", "seamlessly", "robust", "dynamic",
    "cutting-edge", "state-of-the-art", "solution", "empower", "transformative",
    "unlock your potential", "synergy", "holistic", "bespoke", "your journey",
    "we are dedicated to", "our passion", "at the heart of", "in today's fast-paced world",
    "innovador", "robusto", "dinámico", "transformador", "sinergia", "holístico",
    "solución innovadora", "empoderamos", "vanguardia",
]

FALLBACK_CSS_VARS = """
    --copper: #C17A3A;
    --copper-lt: #D9944E;
    --copper-dk: #8A5225;
    --linen: #F5EDD6;
    --linen-dk: #E8DBC0;
    --charcoal: #1A1410;
    --text-on-dk: #F0E8D4;
    --text-body: #4A3825;
    --font-display: 'Cormorant Garamond', Georgia, serif;
    --font-body: 'DM Sans', system-ui, sans-serif;
    --spring: cubic-bezier(0.34, 1.56, 0.64, 1);
"""

FALLBACK_FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">'
)


def _extract_css_vars(index_html: str) -> tuple[str, str]:
    """Return (css_vars_block, font_link_tags) extracted from client index.html."""
    root_match = re.search(r':root\s*\{([^}]+)\}', index_html, re.DOTALL)
    css_vars = root_match.group(1) if root_match else FALLBACK_CSS_VARS

    font_links = "\n".join(
        line.strip() for line in index_html.splitlines()
        if "fonts.googleapis.com" in line or "fonts.gstatic.com" in line
    ) or FALLBACK_FONT_LINKS

    return css_vars, font_links


def _build_kie_prompt(sector: str, topic: str, client_name: str) -> dict:
    scene_map = {
        "restaurante": "An elegant restaurant interior, warm ambient lighting, artisan ceramic dishware on a wooden table",
        "inmobiliaria": "A modern architectural exterior shot of a contemporary home at golden hour, manicured garden",
        "clinica": "A bright modern clinic reception area, clean lines, natural light, potted plants, warm tones",
        "abogado": "A polished law office desk with open books, a pen, and soft side lighting",
        "tienda": "A carefully arranged retail display with artisan products, neutral background, warm accent light",
    }
    default_scene = f"An editorial scene representing the {sector} industry, professional atmosphere, warm natural light"
    scene = next((v for k, v in scene_map.items() if k in (sector or "").lower()), default_scene)

    return {
        "prompt": (
            f"{scene}. Topic context: {topic}. "
            "Shot on 85mm lens, f/2.0, ISO 200, golden hour side light creating warm shadows. "
            "Do not beautify. No CGI. No stock photo aesthetic. Raw, authentic, editorial."
        ),
        "negative_prompt": (
            "blurry, low resolution, plastic, CGI, oversaturated, stock photo, "
            "skin smoothing, airbrushed, generic, anatomy normalization"
        ),
        "settings": {
            "style": "photorealistic, documentary realism",
            "lighting": "golden hour, warm side light",
            "camera_angle": "eye level, 85mm lens",
            "depth_of_field": "shallow, f/2.0",
            "quality": "high detail, unretouched",
        },
        "api_parameters": {
            "aspect_ratio": "16:9",
            "resolution": "1K",
            "output_format": "jpg",
        },
    }


def _generate_hero_image(slug: str, sector: str, topic: str, client_name: str, today_str: str) -> str:
    """Generate hero image via KIE or return placehold.co fallback URL."""
    kie_key = os.getenv("KIE_API_KEY", "")
    prompt_dir = Path("output/prompts") / slug
    asset_dir = Path("output/assets") / slug
    prompt_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = prompt_dir / f"blog-{today_str}.json"
    image_path = asset_dir / f"blog-{today_str}.jpg"

    if not kie_key:
        print("  [WARN] KIE_API_KEY not set — using placehold.co fallback")
        return f"https://placehold.co/1200x675"

    prompt_data = _build_kie_prompt(sector, topic, client_name)
    prompt_path.write_text(json.dumps(prompt_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  Generating hero image via Nano Banana 2...")
    result = subprocess.run(
        [sys.executable, "tools/scripts/generate_kie.py",
         str(prompt_path), str(image_path), "16:9"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  [WARN] KIE generation failed: {result.stderr.strip()}")
        return f"https://placehold.co/1200x675"

    return str(image_path).replace("\\", "/")


def _generate_article(client: dict, topic: str | None, prev_titles: list[str]) -> dict:
    """Call Claude to generate the article. Returns dict with title, meta_description, focus_keyword, html_body."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client_obj = anthropic.Anthropic(api_key=api_key)

    sector = client.get("sector") or "negocio local"
    business_name = client.get("business_name", "")
    prev_titles_str = "\n".join(f"- {t}" for t in prev_titles) if prev_titles else "Ninguno"
    topic_instruction = f'El tema del artículo es: "{topic}".' if topic else (
        f"Elige un tema relevante para el sector {sector} que no repita los anteriores."
    )

    banned = ", ".join(BANNED_WORDS[:15])

    system_prompt = f"""Eres un redactor SEO experto que escribe artículos de blog en español para negocios locales.

REGLAS OBLIGATORIAS:
- Idioma: español neutro, no Spain-specific slang
- Longitud: entre 700 y 1200 palabras en html_body (cuenta solo el texto visible)
- Estructura: un H1 claro + entre 3 y 5 secciones con H2 + párrafos con al menos 2–3 oraciones cada uno
- SEO: incluir la keyword principal en las primeras 100 palabras y en al menos un H2
- Meta description: máximo 155 caracteres
- Un placeholder de enlace interno: <a href="/servicios">[Ver nuestros servicios]</a>
- PROHIBIDAS estas palabras: {banned}
- No inventar datos, estadísticas, premios ni certificaciones
- El contenido debe ser útil, específico y leer como escrito por un experto humano
- No usar bullet lists con más de 5 ítems seguidos

FORMATO DE RESPUESTA — JSON puro, sin markdown, sin texto extra:
{{
  "title": "...",
  "meta_description": "...",
  "focus_keyword": "...",
  "html_body": "..."
}}

html_body debe ser HTML semántico: h2, p, ul/ol, blockquote. Sin estilos inline. Sin div wrappers.
OBLIGATORIO: usa comillas simples en todos los atributos HTML dentro de html_body (href='/servicios' NO href="/servicios") para que el JSON sea válido."""

    user_prompt = f"""Cliente: {business_name}
Sector: {sector}
{topic_instruction}

Artículos publicados anteriormente (evitar repetir):
{prev_titles_str}

Genera el artículo completo ahora."""

    print(f"  Generating article via Claude...")
    message = client_obj.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip possible markdown code fences
    raw = re.sub(r'^```(?:json)?\n?', '', raw)
    raw = re.sub(r'\n?```$', '', raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: extract fields individually via regex to handle unescaped HTML quotes
        try:
            title = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
            meta = re.search(r'"meta_description"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
            keyword = re.search(r'"focus_keyword"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
            # html_body: grab everything between "html_body": " and the final closing "}
            body_m = re.search(r'"html_body"\s*:\s*"(.*)"', raw, re.DOTALL)
            if title and meta and keyword and body_m:
                html_body = body_m.group(1)
                # Unescape JSON escape sequences
                html_body = html_body.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
                return {
                    "title": title.group(1),
                    "meta_description": meta.group(1),
                    "focus_keyword": keyword.group(1),
                    "html_body": html_body,
                }
        except Exception:
            pass
        print(f"Error: Could not parse Claude output as JSON. Raw output:\n{raw[:500]}")
        sys.exit(1)


def _count_words(html_body: str) -> int:
    text = re.sub(r'<[^>]+>', ' ', html_body)
    return len(text.split())


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[áàäâ]', 'a', text)
    text = re.sub(r'[éèëê]', 'e', text)
    text = re.sub(r'[íìïî]', 'i', text)
    text = re.sub(r'[óòöô]', 'o', text)
    text = re.sub(r'[úùüû]', 'u', text)
    text = re.sub(r'ñ', 'n', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')[:60]


def _build_html(client: dict, article: dict, hero_src: str, css_vars: str, font_links: str, today_str: str, word_count: int) -> str:
    business_name = html_lib.escape(client.get("business_name", ""))
    title = html_lib.escape(article["title"])
    meta_desc = html_lib.escape(article["meta_description"])
    html_body = article["html_body"]
    published = datetime.strptime(today_str, "%Y-%m-%d").strftime("%-d de %B de %Y") if sys.platform != "win32" else today_str

    # Resolve relative path for hero image if it's a local file
    hero_img = hero_src
    if not hero_src.startswith("http"):
        hero_img = f"../../assets/{client['slug']}/blog-{today_str}.jpg"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | {business_name}</title>
  <meta name="description" content="{meta_desc}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:image" content="{html_lib.escape(hero_src)}">
  {font_links}
  <link rel="stylesheet" href="https://unpkg.com/aos@2.3.1/dist/aos.css">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    :root {{
      {css_vars.strip()}
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: var(--font-body, 'DM Sans', system-ui, sans-serif);
      background: var(--linen, #F5EDD6);
      color: var(--text-body, #4A3825);
      -webkit-font-smoothing: antialiased;
    }}
    a {{ color: var(--copper, #C17A3A); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    /* Nav */
    .blog-nav {{
      position: sticky; top: 0; z-index: 100;
      background: var(--charcoal, #1A1410);
      padding: 16px 32px;
      display: flex; align-items: center; gap: 16px;
    }}
    .blog-nav a {{ color: var(--text-on-dk, #F0E8D4); font-size: 14px; }}
    .blog-nav .sep {{ color: var(--copper, #C17A3A); }}
    .blog-nav .brand {{ font-family: var(--font-display, Georgia, serif); font-size: 18px; font-weight: 600; }}

    /* Hero */
    .post-hero {{
      position: relative; height: 480px; overflow: hidden;
      display: flex; align-items: flex-end;
    }}
    .post-hero-bg {{
      position: absolute; inset: 0;
      background-image: url('{hero_img}');
      background-size: cover; background-position: center;
      filter: brightness(0.55);
      transition: transform 0.6s var(--ease-out, ease-out);
    }}
    .post-hero:hover .post-hero-bg {{ transform: scale(1.02); }}
    .post-hero-content {{
      position: relative; z-index: 1;
      padding: 48px 10%;
      color: var(--text-on-dk, #F0E8D4);
    }}
    .post-hero h1 {{
      font-family: var(--font-display, Georgia, serif);
      font-size: clamp(28px, 4vw, 56px);
      line-height: 1.15;
      letter-spacing: -0.02em;
      margin-bottom: 12px;
    }}
    .post-meta {{
      font-size: 13px;
      color: var(--copper-lt, #D9944E);
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}

    /* Article */
    .post-body {{
      max-width: 760px;
      margin: 64px auto 80px;
      padding: 0 24px;
      line-height: 1.8;
      font-size: 17px;
    }}
    .post-body h2 {{
      font-family: var(--font-display, Georgia, serif);
      font-size: clamp(22px, 2.5vw, 32px);
      color: var(--charcoal, #1A1410);
      margin: 48px 0 16px;
      letter-spacing: -0.01em;
    }}
    .post-body p {{ margin-bottom: 20px; }}
    .post-body ul, .post-body ol {{
      margin: 0 0 20px 24px;
    }}
    .post-body li {{ margin-bottom: 8px; }}
    .post-body blockquote {{
      border-left: 3px solid var(--copper, #C17A3A);
      padding: 12px 20px;
      margin: 32px 0;
      font-style: italic;
      color: var(--charcoal-lt, #3E2E1E);
      background: var(--linen-dk, #E8DBC0);
      border-radius: 0 4px 4px 0;
    }}
    .post-body a {{
      color: var(--copper, #C17A3A);
      text-decoration: underline;
      text-underline-offset: 3px;
    }}

    /* Footer */
    .post-footer {{
      background: var(--charcoal, #1A1410);
      color: var(--text-on-dk, #F0E8D4);
      text-align: center;
      padding: 40px 24px;
      font-size: 14px;
    }}
    .post-footer a {{ color: var(--copper-lt, #D9944E); }}
  </style>
</head>
<body>

  <nav class="blog-nav">
    <a class="brand" href="../../index.html">{business_name}</a>
    <span class="sep">›</span>
    <a href="../../index.html#blog">Blog</a>
    <span class="sep">›</span>
    <span style="color:var(--copper-lt,#D9944E)">{title[:50]}{'...' if len(title)>50 else ''}</span>
  </nav>

  <div class="post-hero">
    <div class="post-hero-bg"></div>
    <div class="post-hero-content">
      <p class="post-meta" data-aos="fade-up">{today_str} · {word_count} palabras</p>
      <h1 data-aos="fade-up" data-aos-delay="100">{title}</h1>
    </div>
  </div>

  <article class="post-body" data-aos="fade-up" data-aos-delay="200">
    {html_body}
  </article>

  <footer class="post-footer">
    <p>&copy; {date.today().year} {business_name}. <a href="../../index.html">Volver al inicio</a></p>
  </footer>

  <script src="https://unpkg.com/aos@2.3.1/dist/aos.js"></script>
  <script>AOS.init({{ duration: 800, easing: 'ease-out-cubic', once: true }});</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate a SEO blog post for a WAT client")
    parser.add_argument("--client-slug", required=True, help="Client slug (must exist in DB)")
    parser.add_argument("--topic", default=None, help="Optional blog topic in Spanish")
    args = parser.parse_args()

    slug = args.client_slug
    today_str = date.today().isoformat()

    # Step 1 — Validate client
    print(f"[blog-writer] Client: {slug}")
    client = db.get_client(slug)
    if not client:
        print(f"Error: Client '{slug}' not found in database.")
        sys.exit(1)
    client["slug"] = slug

    # Step 2 — Previous posts
    prev_posts = db.list_blog_posts(slug)
    prev_titles = [p["title"] for p in prev_posts]
    print(f"  Previous posts: {len(prev_titles)}")

    # Step 3 — Generate article
    article = _generate_article(client, args.topic, prev_titles)
    topic_used = args.topic or article.get("focus_keyword", "")
    word_count = _count_words(article["html_body"])
    print(f"  Title: {article['title']}")
    print(f"  Word count: {word_count}")

    # Step 4 — Extract client styling
    index_path = Path("output/websites") / slug / "index.html"
    if index_path.exists():
        index_html = index_path.read_text(encoding="utf-8")
        css_vars, font_links = _extract_css_vars(index_html)
        print(f"  Styling extracted from {index_path}")
    else:
        css_vars, font_links = FALLBACK_CSS_VARS, FALLBACK_FONT_LINKS
        print(f"  [WARN] No index.html found for {slug} — using fallback styles")

    # Step 5 — Hero image
    hero_src = _generate_hero_image(
        slug, client.get("sector", ""), topic_used, client.get("business_name", ""), today_str
    )

    # Step 6 — Build HTML
    html = _build_html(client, article, hero_src, css_vars, font_links, today_str, word_count)

    # Save output
    post_slug = _slugify(article["title"])
    blog_dir = Path("output/websites") / slug / "blog"
    blog_dir.mkdir(parents=True, exist_ok=True)
    out_path = blog_dir / f"{slug}-{today_str}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"  Saved: {out_path}")

    # Step 7 — Log to DB
    hero_log_path = hero_src if hero_src.startswith("http") else str(Path("output/assets") / slug / f"blog-{today_str}.jpg")
    row_id = db.add_blog_post(
        slug,
        title=article["title"],
        slug=post_slug,
        word_count=word_count,
        hero_image_path=hero_log_path,
        status="published",
        published_at=today_str,
    )
    print(f"  DB row id: {row_id}")
    print(f"[blog-writer] Done — {out_path}")


if __name__ == "__main__":
    main()
