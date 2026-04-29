"""
build_brief.py

Reads a filled client_brief_template.md and produces .tmp/design_brief.json,
which is consumed by build_website.py to drive personalized 21st.dev queries,
animation palette selection, and competitor-aware design decisions.

Usage:
    python tools/build_brief.py --brief .tmp/client_brief.md
    python tools/build_brief.py --brief templates/client_brief_template.md

Output:
    .tmp/design_brief.json
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Emotion → animation palette
# ---------------------------------------------------------------------------

EMOTION_PALETTES = {
    "trust":      ["clip_path_reveal", "fade_up_stagger", "stat_counter"],
    "excitement": ["marquee", "spring_hover", "grid_entrance"],
    "calm":       ["slow_parallax", "fade_up_stagger", "magnetic_button"],
    "prestige":   ["cursor_aura", "clip_path_reveal", "slow_parallax"],
    "energy":     ["marquee", "spring_hover", "grid_entrance"],
    "warmth":     ["fade_up_stagger", "3d_tilt", "stat_counter"],
}

# Fallback for visual_personality (Demo Mode — no brief)
PERSONALITY_PALETTES = {
    "minimal":   ["slow_parallax", "fade_up_stagger", "magnetic_button"],
    "bold":      ["marquee", "spring_hover", "grid_entrance"],
    "warm":      ["fade_up_stagger", "3d_tilt", "stat_counter"],
    "corporate": ["clip_path_reveal", "fade_up_stagger", "stat_counter"],
    "modern":    ["cursor_aura", "clip_path_reveal", "spring_hover"],
}

# Emotion → visual style keyword (injected into 21st.dev queries)
EMOTION_STYLE = {
    "trust":      "clean minimal trustworthy",
    "excitement": "dynamic bold vibrant",
    "calm":       "minimal serene spacious",
    "prestige":   "editorial luxury serif dark",
    "energy":     "bold kinetic high-contrast",
    "warmth":     "organic warm inviting",
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _strip_inline_comment(val: str) -> str:
    """Strip trailing inline comment (# ...) but only if not inside quotes or brackets."""
    # If value starts with [ or " we skip comment stripping — could contain # hex colors
    stripped = val.strip()
    if stripped.startswith(("[", '"', "'")):
        return stripped
    # Strip # comment only when not inside any bracket or quote
    return re.sub(r"\s+#[^\"'\[\]]*$", "", stripped).strip()


def _extract_value(lines: list[str], key: str) -> str:
    """Extract a single scalar value for a key like '- name: Foo Bar'."""
    pattern = re.compile(rf"^\s*-\s*{re.escape(key)}\s*:\s*(.*)")
    for line in lines:
        m = pattern.match(line)
        if m:
            val = _strip_inline_comment(m.group(1))
            return val if val else ""
    return ""


def _extract_list(lines: list[str], key: str) -> list[str]:
    """Extract a YAML-style inline list value like '- adjectives: ["a", "b", "c"]'."""
    raw = _extract_value(lines, key)
    if not raw or raw in ("[]", ""):
        return []
    # Try JSON parse first
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if x]
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: comma-separated bare values
    return [x.strip().strip('"\'') for x in raw.strip("[]").split(",") if x.strip()]


def parse_brief(path: Path) -> dict:
    """Parse a client_brief_template.md into a structured dict."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    mode = _extract_value(lines, "mode")
    if not mode:
        # Try top-level `mode:` line without dash
        for line in lines:
            m = re.match(r"^mode\s*:\s*(\w+)", line)
            if m:
                mode = m.group(1)
                break
    mode = mode.lower() if mode else "demo"

    return {
        "mode": mode,
        "name": _extract_value(lines, "name"),
        "slug": _extract_value(lines, "slug"),
        "industry": _extract_value(lines, "industry"),
        "location": _extract_value(lines, "location"),
        "target_buyer": _extract_value(lines, "target_buyer"),
        "primary_emotion": _extract_value(lines, "primary_emotion").lower(),
        "primary_cta": _extract_value(lines, "primary_cta").lower(),
        "adjectives": _extract_list(lines, "adjectives"),
        "colors": _extract_list(lines, "colors"),
        "fonts": _extract_list(lines, "fonts"),
        "logo_path": _extract_value(lines, "logo_path"),
        "competitors": _extract_list(lines, "competitors"),
        "differentiator": _extract_value(lines, "differentiator"),
        "forbidden_elements": _extract_list(lines, "forbidden_elements"),
        "existing_assets": _extract_value(lines, "existing_assets"),
    }


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

def build_twentyfirst_queries(brief: dict) -> list[str]:
    """
    Compose 3 targeted 21st.dev search strings from brief data.
    Structure: [adjectives] + [industry] + [emotion style] per query,
    each query aimed at a different section (hero, proof, CTA).
    """
    adj = " ".join(brief.get("adjectives", []))
    industry = brief.get("industry", "")
    emotion = brief.get("primary_emotion", "")
    emotion_style = EMOTION_STYLE.get(emotion, "")
    cta_type = brief.get("primary_cta", "form")

    # Hero query — most important, drives overall aesthetic
    hero_q = " ".join(filter(None, [adj, industry, emotion_style, "hero"]))

    # Social proof / trust section
    proof_q = " ".join(filter(None, [emotion_style, "testimonial trust signal", adj]))

    # CTA section
    cta_q = " ".join(filter(None, [emotion_style, f"call to action {cta_type}", industry]))

    return [hero_q.strip(), proof_q.strip(), cta_q.strip()]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_design_brief(brief_path: Path) -> dict:
    brief = parse_brief(brief_path)
    emotion = brief.get("primary_emotion", "")
    animation_palette = EMOTION_PALETTES.get(emotion, ["fade_up_stagger", "spring_hover", "stat_counter"])

    design_brief = {
        "mode": brief["mode"],
        "name": brief["name"],
        "slug": brief["slug"],
        "industry": brief["industry"],
        "location": brief["location"],
        "target_buyer": brief["target_buyer"],
        "emotional_target": emotion,
        "primary_cta": brief["primary_cta"],
        "adjectives": brief["adjectives"],
        "colors": brief["colors"],
        "fonts": brief["fonts"],
        "logo_path": brief["logo_path"],
        "competitor_urls": brief["competitors"],
        "differentiation_angle": brief["differentiator"],
        "forbidden": brief["forbidden_elements"],
        "existing_assets": brief["existing_assets"],
        "animation_palette": animation_palette,
        "twentyfirst_queries": build_twentyfirst_queries(brief),
    }

    return design_brief


def main():
    parser = argparse.ArgumentParser(description="Build design_brief.json from client brief markdown")
    parser.add_argument("--brief", required=True, help="Path to filled client_brief_template.md")
    parser.add_argument("--output", default=".tmp/design_brief.json", help="Output path for design_brief.json")
    args = parser.parse_args()

    brief_path = Path(args.brief)
    if not brief_path.exists():
        print(f"Error: Brief file not found: {brief_path}")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    design_brief = build_design_brief(brief_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(design_brief, f, ensure_ascii=False, indent=2)

    print(f"[OK] Design brief written to {output_path}")
    print(f"  Mode            : {design_brief['mode']}")
    print(f"  Business        : {design_brief['name']} ({design_brief['industry']})")
    print(f"  Emotion target  : {design_brief['emotional_target']}")
    print(f"  Animation palette: {', '.join(design_brief['animation_palette'])}")
    print(f"\n  21st.dev queries:")
    for i, q in enumerate(design_brief["twentyfirst_queries"], 1):
        print(f"    [{i}] {q}")
    if design_brief.get("competitor_urls"):
        print(f"\n  Competitors to beat:")
        for url in design_brief["competitor_urls"]:
            print(f"    - {url}")


if __name__ == "__main__":
    main()
