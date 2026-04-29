# Client Brief — [Business Name]

mode: client  # demo | client

## Business
- name:
- slug:                # kebab-case, e.g. "garcia-abogados"
- industry:            # Specific: "luxury coastal real estate" not "real estate"
- location:            # City, region

## Audience
- target_buyer:        # One sentence: who they are + what they need. e.g. "Young couples (25-40) looking for their first home in Barcelona"
- primary_emotion:     # trust | excitement | calm | prestige | energy | warmth
- primary_cta:         # call | form | whatsapp | buy

## Brand
- adjectives: []       # Exactly 3 words. e.g. ["trustworthy", "modern", "approachable"]
- colors: []           # Hex codes from existing brand (empty = derive from industry)
- fonts: []            # Existing brand fonts (empty = derive)
- logo_path:           # brand_assets/{slug}/logo.svg or "none"

## Competitive Context
- competitors: []      # 3 URLs — sites we must visually outperform
- differentiator:      # One sentence: what makes this client unique vs those competitors

## Constraints
- forbidden_elements: []  # Design or copy patterns the client explicitly dislikes
- existing_assets:        # brand_assets/{slug}/ or "none"

---
# Notes
# primary_emotion drives animation palette:
#   trust      → clip_path_reveal, fade_up_stagger, stat_counter
#   excitement → marquee, spring_hover, grid_entrance
#   calm       → slow_parallax, fade_up_stagger, magnetic_button
#   prestige   → cursor_aura, clip_path_reveal, slow_parallax
#   energy     → marquee, spring_hover, grid_entrance
#   warmth     → fade_up_stagger, 3d_tilt, stat_counter
