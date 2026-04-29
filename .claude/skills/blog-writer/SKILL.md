---
name: blog-writer
description: Generate a 700–1200 word SEO-optimized blog article in Spanish for a client, with a Nano Banana 2 hero image, styled to match their existing website. Use when the user says "blog", "artículo", "entrada de blog", "blog mensual", or references the blog_mensual service for a client.
argument-hint: "[client-slug] [optional topic]"
---

# blog-writer

Generates a fully styled, SEO-optimized Spanish blog article for a client and saves it to their website directory. Logs every published post to the `blog_posts` table.

## When to Invoke

Trigger this skill whenever:
- The user says "generar artículo", "blog post", "escribir entrada de blog", "blog mensual"
- The user asks to generate, write, or schedule blog content for a client
- The user mentions `blog_mensual` as a service to activate or run
- `run_weekly_blog.py` is being scheduled or tested

---

## Workflow

### Step 1 — Validate Client

```python
import sys; sys.path.insert(0, "tools")
import db
client = db.get_client("client-slug")
# Abort if None
```

### Step 2 — Check Previous Posts (for SEO variety)

```python
previous = db.list_blog_posts("client-slug")
prev_titles = [p["title"] for p in previous]
```

### Step 3 — Generate Article via Claude

Call `claude-sonnet-4-6` with:
- System: enforce Spanish, 700–1200 words, structured H1 + 3–5 H2s, meta description, focus keyword in first 100 words, one internal link placeholder `[LINK: /servicios]`
- User: provide client sector, business name, optional topic, previous titles to avoid
- Response format: JSON `{ "title", "meta_description", "focus_keyword", "html_body" }`
- `html_body` must be semantic HTML (h2, p, ul/ol, blockquote) — no inline styles, no wrapper divs

### Step 4 — Extract Client Styling

Regex `:root { ... }` from `output/websites/{slug}/index.html` to capture all CSS custom properties. Also extract `<link>` tags for Google Fonts.

### Step 5 — Generate Hero Image

Build Dense Narrative JSON (nano-banana-image-gen format):
```json
{
  "prompt": "Editorial photograph representing [sector/topic]. [Camera: 85mm, f/2.0, ISO 200]. [Lighting: golden hour side light]. Do not beautify. No CGI. No stock photo aesthetic.",
  "negative_prompt": "blurry, plastic, CGI, oversaturated, skin smoothing, airbrushed",
  "settings": { "style": "photorealistic, documentary", "quality": "high detail" },
  "api_parameters": { "aspect_ratio": "16:9", "resolution": "1K", "output_format": "jpg" }
}
```

Save prompt to `output/prompts/{slug}/blog-{date}.json`.
Run:
```bash
python tools/scripts/generate_kie.py output/prompts/{slug}/blog-{date}.json output/assets/{slug}/blog-{date}.jpg 16:9
```
Fallback: `https://placehold.co/1200x675` if `KIE_API_KEY` not set.

### Step 6 — Build Blog Post HTML

Save to `output/websites/{slug}/blog/{slug}-{YYYY-MM-DD}.html`.

Structure:
```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | {business_name}</title>
  <meta name="description" content="{meta_description}">
  <!-- Google Fonts from client index.html -->
  <!-- AOS -->
  <link rel="stylesheet" href="https://unpkg.com/aos@2.3.1/dist/aos.css">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Inject all CSS vars from client :root block */
    :root { ... }
    body { font-family: var(--font-body); background: var(--linen); color: var(--text-body); }
    h1,h2,h3 { font-family: var(--font-display); }
    /* Article prose styles using vars */
  </style>
</head>
<body>
  <!-- Nav: link back to index.html -->
  <nav>...</nav>
  <!-- Hero image -->
  <div class="hero" style="background-image: url(../../assets/{slug}/blog-{date}.jpg)">
    <h1 data-aos="fade-up">{title}</h1>
    <p class="meta">{published_date} · {word_count} palabras</p>
  </div>
  <!-- Article body -->
  <article data-aos="fade-up">{html_body}</article>
  <!-- Back link -->
  <footer>...</footer>
  <script src="https://unpkg.com/aos@2.3.1/dist/aos.js"></script>
  <script>AOS.init({ duration: 800, easing: 'ease-out-cubic', once: true });</script>
</body>
</html>
```

### Step 7 — Log to Database

```python
db.add_blog_post(
    slug,
    title=article["title"],
    slug=post_slug,          # kebab-case from title
    word_count=word_count,
    hero_image_path=f"output/assets/{slug}/blog-{date}.jpg",
    status="published",
    published_at=today_iso,
)
```

---

## Output Paths

| Asset | Path |
|---|---|
| Blog HTML | `output/websites/{slug}/blog/{slug}-{YYYY-MM-DD}.html` |
| Hero image | `output/assets/{slug}/blog-{YYYY-MM-DD}.jpg` |
| KIE prompt | `output/prompts/{slug}/blog-{YYYY-MM-DD}.json` |

---

## Edge Cases

- **Client not found:** Abort with clear error message, exit code 1
- **No `output/websites/{slug}/index.html`:** Use fallback vars (`--copper: #C17A3A`, `--linen: #F5EDD6`, Cormorant Garamond + DM Sans)
- **`KIE_API_KEY` missing:** Use placehold.co, log warning
- **Topic not provided:** Claude picks based on client sector and gaps in previous posts
- **Duplicate topic risk:** Pass previous titles in prompt; instruct Claude to choose a different angle
