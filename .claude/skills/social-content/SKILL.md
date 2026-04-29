---
name: social-content
description: Generate a weekly social media content pack (12 posts: 4 Instagram + 4 LinkedIn + 4 Facebook) for a client, with Nano Banana 2 images for Instagram in client's palette (1080x1080). Use when user says "contenido social", "redes sociales", "pack social", "Instagram", "LinkedIn", "Facebook", or references the social_content_pack service.
argument-hint: "[client-slug]"
---

# social-content

Generates a complete weekly social media pack for a client. 12 captions (4 per platform) + 4 Instagram images via Nano Banana 2. Saves to `output/social/{slug}/{YYYY-Www}/`. Logs to `social_content_log`.

## When to Invoke

Trigger this skill whenever:
- The user says "contenido social", "pack de redes", "redes sociales", "pack social"
- The user mentions "Instagram", "LinkedIn", or "Facebook" content for a client
- The user references `social_content_pack` as a service to run or activate
- `run_weekly_social.py` is being scheduled or tested

---

## Workflow

### Step 1 — Validate Client

```python
import sys; sys.path.insert(0, "tools")
import db
client = db.get_client("client-slug")
# Abort if None
```

### Step 2 — Extract Content from Website

Read `output/websites/{slug}/index.html`. Extract via regex/string search:
- **Business name:** `<title>` tag or first `<h1>`
- **Services:** Card titles from service section (look for `<h3>` inside service/feature cards)
- **Tagline/hero copy:** First `<p>` after the hero `<h1>`
- **Testimonials:** Text inside `<blockquote>` or review card elements (max 3)
- **Primary color:** `:root` CSS custom property (prefer `--copper` or `--primary`)
- **Sector:** from `db.get_client()` if available

### Step 3 — Generate 12 Captions via Claude

Call `claude-sonnet-4-6` once with all extracted content. Request JSON array of 12 objects:

```json
[
  {
    "platform": "instagram",
    "index": 1,
    "theme": "service highlight",
    "caption": "...",
    "hashtags": "#diseñoweb #negocio #emprendedor"
  },
  ...
]
```

**Per-platform requirements (enforce in system prompt):**
- **Instagram (4 posts):** 150–220 chars, punchy, 1–2 emoji max per post, end with hashtag block (8–12 tags), focus on visual storytelling
- **LinkedIn (4 posts):** 300–500 chars, professional tone, no hashtag spam (max 3 tags), text-first insight, CTA to visit website or call
- **Facebook (4 posts):** 100–200 chars, conversational, direct CTA ("Llámanos", "Visítanos en"), one question to drive comments

**All posts:** Spanish, no banned AI words (no "innovador", "robusto", "transformador"), content must derive from the extracted website data — no invented services or statistics.

### Step 4 — Generate 4 Instagram Images

For each Instagram post (index 1–4):

Build Dense Narrative JSON prompt matching the post theme + client palette:
```json
{
  "prompt": "Clean flat-lay / editorial scene representing [theme]. Brand colour accent {primary_color}. [85mm lens, f/2.8, ISO 100]. Minimal, modern aesthetic. No text overlay. No people. Direct light, soft shadows. Do not beautify. No CGI.",
  "negative_prompt": "blurry, text, watermark, CGI, oversaturated, stock photo, plastic",
  "settings": { "style": "product photography, editorial", "quality": "high detail" },
  "api_parameters": { "aspect_ratio": "1:1", "resolution": "1K", "output_format": "jpg" }
}
```

Save prompt: `output/prompts/{slug}/social-{week}-ig-{n}.json`
Run:
```bash
python tools/scripts/generate_kie.py \
  output/prompts/{slug}/social-{week}-ig-{n}.json \
  output/social/{slug}/{week}/instagram-{n}.jpg \
  1:1
```
Fallback: `https://placehold.co/1080x1080` if `KIE_API_KEY` not set.

### Step 5 — Save Caption Files

For all 12 posts:
```
output/social/{slug}/{week}/instagram-1.txt
output/social/{slug}/{week}/instagram-2.txt
output/social/{slug}/{week}/instagram-3.txt
output/social/{slug}/{week}/instagram-4.txt
output/social/{slug}/{week}/linkedin-1.txt
...
output/social/{slug}/{week}/facebook-4.txt
```

Each `.txt` file contains the full caption + hashtags, ready to paste.

### Step 6 — Log to Database

```python
import datetime
week = datetime.date.today().isocalendar()[1]
db.log_social_generation(slug, week_of_year=week, post_count=12, output_path=f"output/social/{slug}/{week_str}/")
```

---

## Output Paths

| Asset | Path |
|---|---|
| Instagram images | `output/social/{slug}/{YYYY-Www}/instagram-{1-4}.jpg` |
| All captions | `output/social/{slug}/{YYYY-Www}/{platform}-{1-4}.txt` |
| KIE prompts | `output/prompts/{slug}/social-{week}-ig-{n}.json` |

Week format: ISO week string, e.g. `2026-W16`

---

## Edge Cases

- **Website not found:** Abort — website must exist for content extraction
- **No services in HTML:** Generate posts about the business name + sector only
- **`KIE_API_KEY` missing:** Use placehold.co for Instagram images, log warning
- **Existing week directory:** Overwrite — weekly runs replace the previous week's drafts
- **LinkedIn hashtag spam:** Enforce max 3 hashtags in system prompt; strip extras from Claude output if needed
