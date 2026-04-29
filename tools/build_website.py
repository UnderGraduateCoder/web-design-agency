"""
build_website.py

Usage:
    python tools/build_website.py

Reads .tmp/business_info.json and .tmp/website_copy.json, then generates
a self-contained, responsive output/index.html using Tailwind CSS (CDN)
and Google Fonts. No build step required.

Run gather_business_info.py and generate_copy.py first.

Multi-axis variant system: uses a deterministic hash of the business name
to select from 5 font pairings x 4 layouts x 4 hero styles x 4 service
layouts x 5 visual personalities = 1,600 unique combinations.
"""

import sys
import json
import os
import re
import argparse
import hashlib
import colorsys
import html as html_lib
import subprocess
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def darken_color(hex_color: str, factor: float = 0.65) -> str:
    """Return a darkened version of a hex color for gradient use."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return "#0f2744"
    try:
        r = max(0, int(int(hex_color[0:2], 16) * factor))
        g = max(0, int(int(hex_color[2:4], 16) * factor))
        b = max(0, int(int(hex_color[4:6], 16) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    except ValueError:
        return "#0f2744"


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert hex color to rgba() string."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return f"rgba(0,0,0,{alpha})"
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    except ValueError:
        return f"rgba(0,0,0,{alpha})"


def get_text_color_for_bg(hex_color: str) -> str:
    """Return readable text color (#ffffff or #1a1a1a) for a given background hex."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return "#ffffff"
    try:
        def linearize(c: int) -> float:
            s = c / 255.0
            return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

        r = linearize(int(hex_color[0:2], 16))
        g = linearize(int(hex_color[2:4], 16))
        b = linearize(int(hex_color[4:6], 16))
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return "#1a1a1a" if luminance > 0.35 else "#ffffff"
    except ValueError:
        return "#ffffff"


def generate_color_palette(primary_hex: str) -> dict:
    """Auto-generate 50-900 shades from a single hex color using HSL interpolation."""
    hex_color = primary_hex.lstrip("#")
    if len(hex_color) != 6:
        return {}
    try:
        r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        lightness_map = {
            50: 0.97, 100: 0.93, 200: 0.87, 300: 0.75, 400: 0.62,
            500: 0.50, 600: 0.40, 700: 0.30, 800: 0.22, 900: 0.15,
        }
        palette = {}
        for shade, target_l in lightness_map.items():
            sat = s * (0.7 if shade <= 100 or shade >= 800 else 1.0)
            r2, g2, b2 = colorsys.hls_to_rgb(h, target_l, max(0.0, min(1.0, sat)))
            palette[shade] = "#{:02x}{:02x}{:02x}".format(
                int(r2 * 255), int(g2 * 255), int(b2 * 255)
            )
        return palette
    except (ValueError, ZeroDivisionError):
        return {}


# ---------------------------------------------------------------------------
# Multi-axis design variant system
# ---------------------------------------------------------------------------

def compute_design_seed(business_name: str) -> int:
    """Deterministic seed from business name — same name always gives same design."""
    return int(hashlib.md5(business_name.encode("utf-8")).hexdigest(), 16)


# Axis 1: Font pairings (5 options)
FONT_PAIRINGS = [
    {
        "url": "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Lato:wght@300;400;500;600;700&display=swap",
        "heading": "'Playfair Display', serif",
        "body": "'Lato', sans-serif",
        "label": "Classic",
    },
    {
        "url": "https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600;700&display=swap",
        "heading": "'DM Serif Display', serif",
        "body": "'DM Sans', sans-serif",
        "label": "Editorial",
    },
    {
        "url": "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Libre+Franklin:wght@300;400;500;600;700&display=swap",
        "heading": "'Cormorant Garamond', serif",
        "body": "'Libre Franklin', sans-serif",
        "label": "Refined",
    },
    {
        "url": "https://fonts.googleapis.com/css2?family=Josefin+Sans:wght@500;600;700&family=Work+Sans:wght@300;400;500;600&display=swap",
        "heading": "'Josefin Sans', sans-serif",
        "body": "'Work Sans', sans-serif",
        "label": "Geometric",
    },
    {
        "url": "https://fonts.googleapis.com/css2?family=Bitter:wght@500;600;700&family=Source+Sans+3:wght@300;400;500;600;700&display=swap",
        "heading": "'Bitter', serif",
        "body": "'Source Sans 3', sans-serif",
        "label": "Warm",
    },
]

# Axis 2: Page section order (4 layouts)
LAYOUT_ORDERS = [
    # Layout 0: Classic
    ["hero", "trust", "services", "reviews", "testimonials", "about", "stats", "cta", "faq", "contact"],
    # Layout 1: Story-first
    ["hero", "about", "services", "reviews", "testimonials", "faq", "stats_cta", "contact"],
    # Layout 2: Services-focused
    ["hero", "trust", "services", "stats", "reviews", "testimonials", "about", "cta", "contact"],
    # Layout 3: Minimal
    ["hero", "about_brief", "services", "cta", "contact"],
]

# Axis 5: Visual personality CSS (5 options) — raw CSS, NOT f-strings
PERSONALITY_CSS = [
    # 0: Minimal
    """
    /* Personality: Minimal — airy, restrained */
    .service-card { border: 1px solid #e5e7eb; box-shadow: none; border-radius: 0.5rem; }
    .service-card:hover { transform: translateY(-3px); box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
    .btn-primary { border-radius: 0.25rem; font-weight: 500; letter-spacing: 0.01em; }
    .btn-outline { border-radius: 0.25rem; }
    .review-card { border-radius: 0.5rem; }
    h1, h2, h3 { letter-spacing: -0.02em; }
    """,
    # 1: Bold
    """
    /* Personality: Bold — dramatic, high-impact */
    h1 { font-size: 4.5rem !important; }
    @media (max-width: 768px) { h1 { font-size: 2.5rem !important; } }
    h1, h2, h3 { text-transform: uppercase; letter-spacing: 0.03em; }
    .btn-primary { font-size: 1.05rem; padding: 1.1rem 2.5rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 800; border-radius: 0.25rem; }
    .btn-outline { border-radius: 0.25rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .service-card { border-left: 5px solid var(--accent); border-radius: 0.25rem 0.75rem 0.75rem 0.25rem; }
    .service-card:hover { transform: translateY(-8px); box-shadow: 0 25px 50px rgba(0,0,0,0.15); }
    .review-card { border-radius: 0.5rem; }
    """,
    # 2: Warm / Artisanal
    """
    /* Personality: Warm — crafted, organic feel */
    h1, h2, h3 { letter-spacing: -0.01em; font-weight: 700; }
    .service-card { border-radius: 1.5rem; border: 1px solid rgba(0,0,0,0.04); background: linear-gradient(165deg, #ffffff 0%, #faf8f5 100%); }
    .service-card:hover { transform: translateY(-4px); box-shadow: 0 16px 40px rgba(0,0,0,0.08); }
    .btn-primary { border-radius: 9999px; }
    .btn-outline { border-radius: 9999px; }
    .review-card { border-radius: 1.5rem; }
    .form-input { border-radius: 0.75rem; }
    .nav-bar { border-bottom: none; box-shadow: 0 1px 8px rgba(0,0,0,0.04); }
    """,
    # 3: Corporate
    """
    /* Personality: Corporate — structured, formal */
    h1, h2, h3 { letter-spacing: 0.01em; }
    .service-card { border-radius: 0.375rem; border: none; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .service-card:hover { transform: translateY(-4px); box-shadow: 0 12px 28px rgba(0,0,0,0.1); }
    .btn-primary { border-radius: 0.375rem; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 700; font-size: 0.8125rem; }
    .btn-outline { border-radius: 0.375rem; }
    .review-card { border-radius: 0.375rem; }
    .form-input { border-radius: 0.375rem; }
    """,
    # 4: Modern
    """
    /* Personality: Modern — gradients, glass, depth */
    h1, h2, h3 { letter-spacing: -0.03em; }
    .service-card { background: rgba(255,255,255,0.85); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.4); border-radius: 1rem; }
    .service-card:hover { transform: translateY(-6px); box-shadow: 0 20px 40px rgba(0,0,0,0.12); background: rgba(255,255,255,0.95); }
    .btn-primary { border-radius: 0.75rem; background: linear-gradient(135deg, var(--accent) 0%, var(--primary) 100%); }
    .btn-outline { border-radius: 0.75rem; }
    .review-card { border-radius: 1rem; backdrop-filter: blur(8px); }
    .nav-bar { background-color: rgba(255,255,255,0.7); }
    """,
]

PERSONALITY_LABELS = ["Minimal", "Bold", "Warm", "Corporate", "Modern"]


def compute_variant_axes(business_name: str) -> dict:
    """Compute all design axes from business name. Deterministic."""
    seed = compute_design_seed(business_name)
    return {
        "seed": seed,
        "font_id": seed % 5,
        "layout_id": (seed // 5) % 4,
        "hero_id": (seed // 20) % 4,
        "services_id": (seed // 80) % 4,
        "personality_id": (seed // 320) % 5,
    }


# ---------------------------------------------------------------------------
# Textile trust badges (replaces law-firm badges)
# ---------------------------------------------------------------------------

TRUST_BADGE_SETS = {
    "embroidery": [
        ("Bordado a Medida", "shield"),
        ("Maquinaria Industrial", "cog"),
        ("Entrega Puntual", "clock"),
    ],
    "home_textiles": [
        ("Tejidos Certificados", "shield"),
        ("Calidad Garantizada", "star"),
        ("Env&iacute;o a Domicilio", "truck"),
    ],
    "sewing": [
        ("Patronaje Profesional", "scissors"),
        ("Acabado Impecable", "star"),
        ("Plazos Garantizados", "clock"),
    ],
    "fashion": [
        ("Producci&oacute;n Local", "shield"),
        ("Tendencias Actuales", "star"),
        ("Atenci&oacute;n Personalizada", "heart"),
    ],
    "b2b": [
        ("Pedidos al por Mayor", "truck"),
        ("Muestras Gratuitas", "gift"),
        ("Facturaci&oacute;n Flexible", "shield"),
    ],
    "default": [
        ("Calidad Profesional", "shield"),
        ("Experiencia Contrastada", "star"),
        ("Compromiso y Garant&iacute;a", "clock"),
    ],
}

BADGE_SVGS = {
    "shield": '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>',
    "clock": '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
    "star": '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>',
    "truck": '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10l2-1 2 1 2-1 2 1m0 0V6m0 10l2-1 2 1 2-1 2 1V6a1 1 0 00-1-1h-4a1 1 0 00-1 1"/></svg>',
    "gift": '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v13m0-13V6a4 4 0 00-4-4c-1.5 0-2.8.8-3.5 2M12 8V6a4 4 0 014-4c1.5 0 2.8.8 3.5 2M6 8h12a2 2 0 012 2v2H4v-2a2 2 0 012-2zM4 12h16v7a2 2 0 01-2 2H6a2 2 0 01-2-2v-7z"/></svg>',
    "heart": '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>',
    "scissors": '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M14.121 14.121L19 19m-7-7l7-7m-7 7l-2.879 2.879M12 12L9.121 9.121m0 5.758a3 3 0 10-4.243 4.243 3 3 0 004.243-4.243zm0-5.758a3 3 0 10-4.243-4.243 3 3 0 004.243 4.243z"/></svg>',
    "cog": '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>',
}


def detect_badge_set(business_info: dict) -> str:
    """Pick the best trust badge set based on business info."""
    name_lower = (business_info.get("business_name", "") + " " + business_info.get("industry", "")).lower()
    bt = business_info.get("business_type", {})
    specialty = bt.get("specialty", "")
    customer = bt.get("customer_focus", "")

    if specialty == "embroidery" or "bordado" in name_lower:
        return "embroidery"
    if specialty == "home_textiles" or any(w in name_lower for w in ["hogar", "home", "ropa de cama"]):
        return "home_textiles"
    if specialty in ("sewing_workshop", "sample_making") or any(w in name_lower for w in ["confeccion", "costur", "corte"]):
        return "sewing"
    if specialty == "fashion_retail" or any(w in name_lower for w in ["moda", "boutique"]):
        return "fashion"
    if customer == "b2b":
        return "b2b"
    return "default"


# ---------------------------------------------------------------------------
# Heroicons SVG paths (inline, no external dependencies)
# ---------------------------------------------------------------------------

ICONS = [
    '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>',
]

SOCIAL_ICONS = {
    "facebook": '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>',
    "instagram": '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>',
    "linkedin": '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
    "twitter": '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.747l7.73-8.835L1.254 2.25H8.08l4.259 5.632L18.244 2.25zm-1.161 17.52h1.833L7.084 4.126H5.117L17.083 19.77z"/></svg>',
}


# ---------------------------------------------------------------------------
# Shared section builders (unchanged from original)
# ---------------------------------------------------------------------------

def build_stats_html(stats: list, accent: str) -> str:
    items = []
    for stat in stats:
        items.append(f"""
        <div class="text-center px-8">
          <div class="text-5xl font-extrabold mb-3" style="color: {accent};">{stat.get("number", "")}</div>
          <div class="text-gray-300 text-sm uppercase tracking-widest font-medium">{stat.get("label", "")}</div>
        </div>""")
    return "\n".join(items)


def is_spanish_mobile(phone: str) -> bool:
    """Return True if phone appears to be a Spanish mobile number (6xx or 7xx)."""
    digits = re.sub(r"[\s\-\+\(\)]", "", phone or "")
    if digits.startswith("34"):
        digits = digits[2:]
    return bool(digits) and digits[0] in ("6", "7")


def build_contact_info_html(contact: dict, accent: str) -> str:
    accent_bg = hex_to_rgba(accent, 0.12)
    items = []

    email_svg = '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>'
    phone_svg = '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>'
    addr_svg = '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>'

    if contact.get("email"):
        items.append(f"""
      <div class="flex items-start gap-4">
        <div class="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0" style="background-color: {accent_bg}; color: {accent};">{email_svg}</div>
        <div>
          <div class="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">Email</div>
          <a href="mailto:{contact['email']}" class="text-gray-900 font-medium hover:underline">{contact['email']}</a>
        </div>
      </div>""")

    if contact.get("phone"):
        phone = contact["phone"]
        phone_digits = re.sub(r"[\s\-\+\(\)]", "", phone).lstrip("34")
        wa_svg = '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.138.566 4.14 1.548 5.877L0 24l6.305-1.527A11.95 11.95 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-1.847 0-3.597-.487-5.126-1.34l-.367-.217-3.742.906.946-3.65-.237-.382A9.944 9.944 0 012 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10z"/></svg>'
        if is_spanish_mobile(phone):
            wa_bg = "rgba(37,211,102,0.12)"
            items.append(f"""
      <div class="flex items-start gap-4">
        <div class="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0" style="background-color: {wa_bg}; color: #25D366;">{wa_svg}</div>
        <div>
          <div class="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">WhatsApp</div>
          <a href="https://wa.me/34{phone_digits}" class="font-medium hover:underline" style="color: #25D366;" target="_blank" rel="noopener noreferrer">{phone}</a>
        </div>
      </div>""")
        else:
            items.append(f"""
      <div class="flex items-start gap-4">
        <div class="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0" style="background-color: {accent_bg}; color: {accent};">{phone_svg}</div>
        <div>
          <div class="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">Tel&eacute;fono</div>
          <a href="tel:{phone}" class="text-gray-900 font-medium hover:underline">{phone}</a>
        </div>
      </div>""")

    if contact.get("address"):
        items.append(f"""
      <div class="flex items-start gap-4">
        <div class="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0" style="background-color: {accent_bg}; color: {accent};">{addr_svg}</div>
        <div>
          <div class="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">Direcci&oacute;n</div>
          <div class="text-gray-900 font-medium">{contact['address']}</div>
        </div>
      </div>""")

    return "\n".join(items)


def build_social_html(social_links: dict, accent: str) -> str:
    links = []
    for platform, url in social_links.items():
        if url and platform in SOCIAL_ICONS:
            links.append(
                f'<a href="{url}" target="_blank" rel="noopener" class="w-9 h-9 rounded-lg flex items-center justify-center text-white transition-opacity hover:opacity-100" style="background-color: rgba(255,255,255,0.12); opacity: 0.7;">'
                f"{SOCIAL_ICONS[platform]}</a>"
            )
    return f'<div class="flex gap-3">{"".join(links)}</div>' if links else ""


def build_about_paragraphs(paragraphs: list, text_color: str = "#4b5563") -> str:
    return "\n".join(
        f'<p class="leading-relaxed mb-5 last:mb-0" style="color: {text_color};" data-aos="fade-up">{p}</p>'
        for p in paragraphs
    )


def build_star_svg(filled: bool) -> str:
    color = "#f59e0b" if filled else "#d1d5db"
    return (
        f'<svg class="w-4 h-4" fill="{color}" viewBox="0 0 24 24">'
        '<path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915'
        "c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755"
        " 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197"
        "-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588"
        '-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>'
    )


def build_star_row(rating: int) -> str:
    return "".join(build_star_svg(i < rating) for i in range(5))


def build_reviews_html(google_places: dict, accent: str) -> str:
    reviews = google_places.get("reviews", [])
    if not reviews:
        return ""

    cards = []
    google_svg = '<svg class="w-5 h-5 ml-auto flex-shrink-0 opacity-40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21.805 10.023H12v3.977h5.618C17.012 16.303 14.74 18 12 18c-3.314 0-6-2.686-6-6s2.686-6 6-6c1.516 0 2.896.564 3.942 1.483l2.822-2.822C16.965 3.204 14.641 2 12 2 6.477 2 2 6.477 2 12s4.477 10 10 10c5.523 0 10-4.477 10-10 0-.67-.069-1.325-.195-1.977z" fill="#4285F4"/></svg>'
    for r in reviews:
        stars = build_star_row(int(r.get("rating", 5)))
        raw_text = r.get("text", "").strip()
        if raw_text:
            text = raw_text.replace('"', "&quot;")
            if len(text) > 200:
                text = text[:197] + "..."
            quote_html = f'<p class="text-gray-600 text-sm leading-relaxed flex-1">"{text}"</p>'
        else:
            quote_html = ""
        author = r.get("author", "Anonymous")
        rel_time = r.get("relative_time", "")
        delay = len(cards) * 100
        cards.append(f"""
        <div class="review-card bg-white rounded-2xl p-6 shadow-sm border border-gray-100 flex flex-col gap-4" data-aos="fade-up" data-aos-delay="{delay}">
          <div class="flex gap-0.5">{stars}</div>
          {quote_html}
          <div class="flex items-center gap-3 pt-2 border-t border-gray-50">
            <div class="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0" style="background-color: {accent};">{author[0].upper()}</div>
            <div>
              <div class="text-sm font-semibold text-gray-800">{author}</div>
              <div class="text-xs text-gray-400">{rel_time}</div>
            </div>
            {google_svg}
          </div>
        </div>""")

    rating = google_places.get("rating")
    review_count = google_places.get("review_count")
    rating_badge = ""
    if rating and review_count:
        rating_badge = (
            f'<span class="inline-flex items-center gap-1.5 text-sm font-medium text-gray-400">'
            f'<svg class="w-4 h-4 opacity-60" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M21.805 10.023H12v3.977h5.618C17.012 16.303 14.74 18 12 18c-3.314 0-6-2.686-6-6s2.686-6 6-6c1.516 0 2.896.564 3.942 1.483l2.822-2.822C16.965 3.204 14.641 2 12 2 6.477 2 2 6.477 2 12s4.477 10 10 10c5.523 0 10-4.477 10-10 0-.67-.069-1.325-.195-1.977z" fill="#4285F4"/></svg>'
            f'{rating} \u2605 &middot; {review_count:,} rese&ntilde;as'
            f'</span>'
        )

    cols = "lg:grid-cols-3" if len(cards) >= 3 else ("lg:grid-cols-2" if len(cards) == 2 else "lg:grid-cols-1")
    return f"""
  <section class="py-20 md:py-28" style="background-color: var(--secondary);">
    <div class="max-w-6xl mx-auto px-6">
      <div class="text-center mb-14" data-aos="fade-up">
        <h2 class="text-3xl md:text-4xl font-bold inline-flex items-center flex-wrap justify-center gap-3" style="color: var(--secondary-text);">
          Rese&ntilde;as de Google
          {rating_badge}
        </h2>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 {cols} gap-6">
        {"".join(cards)}
      </div>
    </div>
  </section>
"""


def build_trust_badges_html(business_info: dict, accent: str) -> str:
    """Render textile-appropriate trust badges."""
    badge_set_key = detect_badge_set(business_info)
    badges = TRUST_BADGE_SETS.get(badge_set_key, TRUST_BADGE_SETS["default"])
    items = "".join(
        f'<div class="flex items-center gap-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">'
        f'<span style="color:{accent};">{BADGE_SVGS.get(icon, BADGE_SVGS["shield"])}</span>{label}</div>'
        for label, icon in badges
    )
    return f"""
  <div class="bg-gray-50 border-b border-gray-100 py-2.5">
    <div class="max-w-6xl mx-auto px-6 flex items-center justify-center gap-8 flex-wrap">
      {items}
    </div>
  </div>
"""


def build_emergency_bar(phone: str) -> str:
    """Render a sticky 'Call Now' bar at the bottom on mobile."""
    if not phone:
        return ""
    phone_svg = '<svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>'
    return f"""
  <div class="fixed bottom-0 left-0 right-0 z-50 md:hidden" style="background-color: var(--accent);">
    <a href="tel:{phone}" class="flex items-center justify-center gap-3 py-4 text-white font-bold text-sm uppercase tracking-widest">
      {phone_svg}
      Llamar Ahora &mdash; {phone}
    </a>
  </div>
  <div class="h-14 md:hidden"></div>
"""


def build_faq_html(faq_items: list, accent: str) -> str:
    """Render an FAQ accordion section."""
    if not faq_items:
        return ""
    items_html = []
    for i, item in enumerate(faq_items):
        q = html_lib.escape(item.get("question", ""))
        a = html_lib.escape(item.get("answer", ""))
        delay = i * 60
        items_html.append(f"""
        <div class="faq-item border border-gray-100 rounded-xl overflow-hidden" data-aos="fade-up" data-aos-delay="{delay}">
          <button
            class="w-full flex items-center justify-between gap-4 px-6 py-5 text-left font-semibold text-gray-900 hover:bg-gray-50 transition-colors"
            onclick="toggleFaq(this)"
            aria-expanded="false"
          >
            <span>{q}</span>
            <svg class="faq-icon w-5 h-5 flex-shrink-0 transition-transform duration-200 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
            </svg>
          </button>
          <div class="faq-answer hidden px-6 pb-5">
            <p class="text-gray-600 leading-relaxed text-sm">{a}</p>
          </div>
        </div>""")
    return f"""
  <section class="py-20 md:py-28 bg-white">
    <div class="max-w-3xl mx-auto px-6">
      <div class="text-center mb-12" data-aos="fade-up">
        <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color: var(--accent);">Preguntas Frecuentes</div>
        <h2 class="text-3xl md:text-4xl font-bold text-gray-900">Lo que necesitas saber</h2>
      </div>
      <div class="space-y-3">
        {"".join(items_html)}
      </div>
    </div>
  </section>
"""


def build_schema_org(business_info: dict, website_copy: dict) -> str:
    """Generate Schema.org LocalBusiness JSON-LD."""
    name = business_info.get("business_name", "")
    industry = business_info.get("industry", "").lower()
    contact = business_info.get("contact", {})
    google_places = business_info.get("google_places") or {}
    seo = website_copy.get("seo", {})

    type_map = [
        (["law", "legal", "abogad", "notari"], "LegalService"),
        (["dental", "dentist"], "Dentist"),
        (["medical", "doctor", "clinic", "médic"], "MedicalBusiness"),
        (["restaurant", "restaurante", "cafe", "café", "food", "comida"], "Restaurant"),
        (["gym", "fitness", "gimnas", "yoga", "spa"], "HealthClub"),
        (["beauty", "belleza", "salon", "peluquer"], "BeautySalon"),
        (["hotel", "hostel", "alojamiento"], "LodgingBusiness"),
        (["accounti", "contab"], "AccountingService"),
        (["real estate", "inmobili"], "RealEstateAgent"),
        (["electric", "plumb", "fontaner", "hvac", "roofing", "construcc"], "HomeAndConstructionBusiness"),
    ]
    schema_type = "LocalBusiness"
    for keywords, t in type_map:
        if any(kw in industry for kw in keywords):
            schema_type = t
            break

    schema: dict = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": name,
        "description": seo.get("meta_description") or business_info.get("about", ""),
    }
    if contact.get("phone"):
        schema["telephone"] = contact["phone"]
    if contact.get("email"):
        schema["email"] = contact["email"]
    if contact.get("address"):
        schema["address"] = {"@type": "PostalAddress", "streetAddress": contact["address"]}
    rating = google_places.get("rating")
    review_count = google_places.get("review_count")
    if rating and review_count:
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(rating),
            "reviewCount": str(review_count),
        }
    return f'<script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n</script>'


def build_testimonials_html(testimonials: list, accent: str) -> str:
    """Render synthesized testimonials (from generate_copy.py)."""
    if not testimonials:
        return ""
    cards = []
    for i, t in enumerate(testimonials):
        quote = html_lib.escape(t.get("quote", ""))
        author = html_lib.escape(t.get("author", ""))
        role = html_lib.escape(t.get("role", ""))
        initial = author[0].upper() if author else "C"
        delay = i * 100
        five_stars = "".join(build_star_svg(True) for _ in range(5))
        cards.append(f"""
        <div class="bg-white rounded-2xl p-7 shadow-sm border border-gray-100" data-aos="fade-up" data-aos-delay="{delay}">
          <div class="flex gap-1 mb-4">{five_stars}</div>
          <p class="text-gray-700 leading-relaxed mb-5 text-sm italic">&ldquo;{quote}&rdquo;</p>
          <div class="flex items-center gap-3 pt-4 border-t border-gray-50">
            <div class="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0" style="background-color: {accent};">{initial}</div>
            <div>
              <div class="text-sm font-semibold text-gray-900">{author}</div>
              <div class="text-xs text-gray-400">{role}</div>
            </div>
          </div>
        </div>""")
    cols = "lg:grid-cols-3" if len(cards) >= 3 else ("lg:grid-cols-2" if len(cards) == 2 else "lg:grid-cols-1")
    bg = hex_to_rgba(accent, 0.06)
    return f"""
  <section class="py-20 md:py-28" style="background-color: {bg};">
    <div class="max-w-6xl mx-auto px-6">
      <div class="text-center mb-12" data-aos="fade-up">
        <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color: var(--accent);">Lo que dicen</div>
        <h2 class="text-3xl md:text-4xl font-bold text-gray-900">Clientes que conf&iacute;an en nosotros</h2>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 {cols} gap-6">
        {"".join(cards)}
      </div>
    </div>
  </section>
"""


# ---------------------------------------------------------------------------
# VARIANT SECTION BUILDERS — Hero (4 styles)
# ---------------------------------------------------------------------------

def _hero_media(hero_video_url, hero_video_poster, hero_image_path):
    """Return (section_open_tag, overlay_html) for the hero background."""
    if hero_video_url:
        poster = hero_video_poster or hero_image_path or ""
        poster_attr = f' poster="{poster}"' if poster else ""
        section_open = '<section class="relative overflow-hidden py-28 md:py-36" style="background:#000;">'
        overlay = (
            f'<video class="hero-video absolute inset-0 w-full h-full object-cover" '
            f'autoplay muted loop playsinline{poster_attr}>'
            f'<source src="{hero_video_url}" type="video/mp4">'
            f'</video>'
            f'<div class="hero-video-overlay absolute inset-0"></div>'
        )
    elif hero_image_path:
        section_open = (
            f'<section class="relative overflow-hidden py-28 md:py-36" '
            f'style="background: url(\'{hero_image_path}\') center/cover no-repeat;">'
        )
        overlay = '<div class="absolute inset-0" style="background: rgba(0,0,0,0.55);"></div>'
    else:
        section_open = '<section class="hero-bg relative overflow-hidden py-28 md:py-36">'
        overlay = '<div class="absolute inset-0 dot-pattern"></div>'
    return section_open, overlay


def build_hero_centered(hero, tagline, hero_video_url, hero_video_poster, hero_image_path):
    """Hero variant 0: Centered text over full-width media."""
    section_open, overlay = _hero_media(hero_video_url, hero_video_poster, hero_image_path)
    return f"""
  {section_open}
    {overlay}
    <div class="relative max-w-5xl mx-auto px-6 text-center text-white" style="z-index:2;">
      <div class="inline-flex items-center gap-2 bg-white bg-opacity-15 border border-white border-opacity-20 text-white text-xs font-semibold uppercase tracking-widest px-4 py-2 rounded-full mb-8">
        <span style="color: var(--accent);">&#9679;</span>
        {tagline}
      </div>
      <h1 class="text-4xl sm:text-5xl md:text-6xl font-extrabold leading-tight tracking-tight mb-6">
        {hero.get("headline", "")}
      </h1>
      <p class="text-lg md:text-xl max-w-2xl mx-auto mb-10 leading-relaxed" style="color: rgba(255,255,255,0.82);">
        {hero.get("subheadline", tagline)}
      </p>
      <div class="flex flex-col sm:flex-row gap-4 justify-center">
        <a href="#contact" class="btn-primary">{hero.get("cta_primary", "Cont&aacute;ctanos")}</a>
        <a href="#services" class="btn-outline">{hero.get("cta_secondary", "Ver Servicios")}</a>
      </div>
    </div>
  </section>
"""


def build_hero_left(hero, tagline, hero_video_url, hero_video_poster, hero_image_path):
    """Hero variant 1: Left-aligned text with decorative right side."""
    section_open, overlay = _hero_media(hero_video_url, hero_video_poster, hero_image_path)
    return f"""
  {section_open}
    {overlay}
    <div class="relative max-w-6xl mx-auto px-6 text-white" style="z-index:2;">
      <div class="max-w-xl">
        <div class="inline-flex items-center gap-2 bg-white bg-opacity-15 border border-white border-opacity-20 text-white text-xs font-semibold uppercase tracking-widest px-4 py-2 rounded-full mb-8">
          <span style="color: var(--accent);">&#9679;</span>
          {tagline}
        </div>
        <h1 class="text-4xl sm:text-5xl md:text-6xl font-extrabold leading-tight tracking-tight mb-6">
          {hero.get("headline", "")}
        </h1>
        <p class="text-lg md:text-xl mb-10 leading-relaxed" style="color: rgba(255,255,255,0.82);">
          {hero.get("subheadline", tagline)}
        </p>
        <div class="flex flex-col sm:flex-row gap-4">
          <a href="#contact" class="btn-primary">{hero.get("cta_primary", "Cont&aacute;ctanos")}</a>
          <a href="#services" class="btn-outline">{hero.get("cta_secondary", "Ver Servicios")}</a>
        </div>
      </div>
    </div>
  </section>
"""


def build_hero_diagonal(hero, tagline, hero_video_url, hero_video_poster, hero_image_path):
    """Hero variant 2: Centered text with diagonal clip-path bottom edge."""
    section_open, overlay = _hero_media(hero_video_url, hero_video_poster, hero_image_path)
    # Replace closing </section> tag style — add clip-path via inline style
    section_open = section_open.replace(
        'py-28 md:py-36"',
        'py-32 md:py-44 pb-40 md:pb-52" style="' +
        section_open.split('style="')[1] if 'style="' in section_open else
        'py-28 md:py-36"'
    )
    # Simpler approach: wrap in a div with clip-path
    _, overlay = _hero_media(hero_video_url, hero_video_poster, hero_image_path)
    if hero_video_url:
        poster = hero_video_poster or hero_image_path or ""
        poster_attr = f' poster="{poster}"' if poster else ""
        bg_style = 'background:#000;'
        media_html = (
            f'<video class="hero-video absolute inset-0 w-full h-full object-cover" '
            f'autoplay muted loop playsinline{poster_attr}>'
            f'<source src="{hero_video_url}" type="video/mp4">'
            f'</video>'
            f'<div class="hero-video-overlay absolute inset-0"></div>'
        )
    elif hero_image_path:
        bg_style = f"background: url('{hero_image_path}') center/cover no-repeat;"
        media_html = '<div class="absolute inset-0" style="background: rgba(0,0,0,0.55);"></div>'
    else:
        bg_style = ''
        media_html = '<div class="absolute inset-0 dot-pattern"></div>'

    return f"""
  <div style="clip-path: polygon(0 0, 100% 0, 100% 85%, 0 100%);">
    <section class="{'hero-bg ' if not bg_style else ''}relative overflow-hidden py-32 md:py-44 pb-44 md:pb-56" style="{bg_style}">
      {media_html}
      <div class="relative max-w-5xl mx-auto px-6 text-center text-white" style="z-index:2;">
        <div class="inline-flex items-center gap-2 bg-white bg-opacity-15 border border-white border-opacity-20 text-white text-xs font-semibold uppercase tracking-widest px-4 py-2 rounded-full mb-8">
          <span style="color: var(--accent);">&#9679;</span>
          {tagline}
        </div>
        <h1 class="text-4xl sm:text-5xl md:text-6xl font-extrabold leading-tight tracking-tight mb-6">
          {hero.get("headline", "")}
        </h1>
        <p class="text-lg md:text-xl max-w-2xl mx-auto mb-10 leading-relaxed" style="color: rgba(255,255,255,0.82);">
          {hero.get("subheadline", tagline)}
        </p>
        <div class="flex flex-col sm:flex-row gap-4 justify-center">
          <a href="#contact" class="btn-primary">{hero.get("cta_primary", "Cont&aacute;ctanos")}</a>
          <a href="#services" class="btn-outline">{hero.get("cta_secondary", "Ver Servicios")}</a>
        </div>
      </div>
    </section>
  </div>
"""


def build_hero_split(hero, tagline, name, primary, hero_video_url, hero_video_poster, hero_image_path):
    """Hero variant 3: Two-column split — text left on primary bg, media right."""
    primary_text = get_text_color_for_bg(primary)
    if hero_video_url:
        poster = hero_video_poster or hero_image_path or ""
        poster_attr = f' poster="{poster}"' if poster else ""
        media_col = (
            f'<div class="relative overflow-hidden rounded-2xl min-h-64 md:min-h-full" style="background:#000;">'
            f'<video class="hero-video absolute inset-0 w-full h-full object-cover" autoplay muted loop playsinline{poster_attr}>'
            f'<source src="{hero_video_url}" type="video/mp4"></video></div>'
        )
    elif hero_image_path:
        media_col = f'<div class="rounded-2xl min-h-64 md:min-h-full bg-cover bg-center" style="background-image: url(\'{hero_image_path}\');"></div>'
    else:
        media_col = (
            f'<div class="rounded-2xl min-h-64 md:min-h-full flex items-center justify-center" style="background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.1);">'
            f'<span class="text-6xl font-extrabold opacity-10" style="color: {primary_text};">{html_lib.escape(name[:2].upper())}</span></div>'
        )

    return f"""
  <section class="relative overflow-hidden" style="background: {primary};">
    <div class="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-0">
      <div class="px-8 md:px-16 py-24 md:py-36 flex flex-col justify-center">
        <div class="inline-flex items-center gap-2 bg-white bg-opacity-10 border border-white border-opacity-15 text-xs font-semibold uppercase tracking-widest px-4 py-2 rounded-full mb-8 self-start" style="color: {primary_text};">
          <span style="color: var(--accent);">&#9679;</span>
          {tagline}
        </div>
        <h1 class="text-4xl sm:text-5xl md:text-5xl lg:text-6xl font-extrabold leading-tight tracking-tight mb-6" style="color: {primary_text};">
          {hero.get("headline", "")}
        </h1>
        <p class="text-lg mb-10 leading-relaxed" style="color: {primary_text}; opacity: 0.8;">
          {hero.get("subheadline", tagline)}
        </p>
        <div class="flex flex-col sm:flex-row gap-4">
          <a href="#contact" class="btn-primary">{hero.get("cta_primary", "Cont&aacute;ctanos")}</a>
          <a href="#services" class="btn-outline" style="border-color: {primary_text}; color: {primary_text}; opacity: 0.8;">{hero.get("cta_secondary", "Ver Servicios")}</a>
        </div>
      </div>
      <div class="hidden md:block">
        {media_col}
      </div>
    </div>
  </section>
"""


# ---------------------------------------------------------------------------
# VARIANT SECTION BUILDERS — Services (4 layouts)
# ---------------------------------------------------------------------------

def build_services_grid(services: list, accent: str) -> str:
    """Services variant 0: Classic card grid."""
    accent_bg = hex_to_rgba(accent, 0.12)
    cards = []
    for i, service in enumerate(services):
        icon = ICONS[i % len(ICONS)]
        delay = i * 100
        cards.append(f"""
        <div class="service-card bg-white rounded-2xl p-8 shadow-sm border border-gray-100 group" data-aos="fade-up" data-aos-delay="{delay}">
          <div class="w-12 h-12 rounded-xl flex items-center justify-center mb-6 transition-colors duration-300" style="background-color: {accent_bg}; color: {accent};">
            {icon}
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-3">{service.get("headline", service.get("name", ""))}</h3>
          <p class="text-gray-500 leading-relaxed text-sm">{service.get("description", "")}</p>
        </div>""")
    count = len(services)
    grid_cols = "lg:grid-cols-3" if count >= 3 else ("lg:grid-cols-2" if count == 2 else "lg:grid-cols-1")
    return f"""
  <section id="services" class="py-24 md:py-32 bg-white">
    <div class="max-w-6xl mx-auto px-6">
      <div class="text-center mb-16" data-aos="fade-up">
        <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color: var(--accent);">Lo que ofrecemos</div>
        <h2 class="text-3xl md:text-4xl font-bold text-gray-900">Nuestros Servicios</h2>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 {grid_cols} gap-8">
        {"".join(cards)}
      </div>
    </div>
  </section>
"""


def build_services_alternating(services: list, accent: str) -> str:
    """Services variant 1: Full-width alternating rows (text left/right)."""
    accent_bg = hex_to_rgba(accent, 0.12)
    rows = []
    for i, service in enumerate(services):
        icon = ICONS[i % len(ICONS)]
        delay = i * 100
        reverse = "md:flex-row-reverse" if i % 2 == 1 else ""
        bg = 'style="background-color: var(--secondary);"' if i % 2 == 1 else ""
        rows.append(f"""
        <div class="flex flex-col {reverse} md:flex-row items-center gap-8 md:gap-16 py-12 md:py-16 px-6 md:px-12 rounded-2xl" {bg} data-aos="fade-up" data-aos-delay="{delay}">
          <div class="flex-shrink-0 w-16 h-16 rounded-2xl flex items-center justify-center" style="background-color: {accent_bg}; color: {accent};">
            {icon}
          </div>
          <div class="flex-1 text-center md:text-left">
            <h3 class="text-xl font-bold text-gray-900 mb-3">{service.get("headline", service.get("name", ""))}</h3>
            <p class="text-gray-500 leading-relaxed">{service.get("description", "")}</p>
          </div>
        </div>""")
    return f"""
  <section id="services" class="py-24 md:py-32 bg-white">
    <div class="max-w-4xl mx-auto px-6">
      <div class="text-center mb-16" data-aos="fade-up">
        <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color: var(--accent);">Lo que ofrecemos</div>
        <h2 class="text-3xl md:text-4xl font-bold text-gray-900">Nuestros Servicios</h2>
      </div>
      <div class="space-y-4">
        {"".join(rows)}
      </div>
    </div>
  </section>
"""


def build_services_list(services: list, accent: str) -> str:
    """Services variant 2: Compact icon+text list, no cards."""
    accent_bg = hex_to_rgba(accent, 0.12)
    items = []
    for i, service in enumerate(services):
        icon = ICONS[i % len(ICONS)]
        delay = i * 80
        items.append(f"""
        <div class="flex items-start gap-5 py-6 border-b border-gray-100 last:border-0" data-aos="fade-up" data-aos-delay="{delay}">
          <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 mt-1" style="background-color: {accent_bg}; color: {accent};">
            {icon}
          </div>
          <div>
            <h3 class="text-lg font-semibold text-gray-900 mb-1">{service.get("headline", service.get("name", ""))}</h3>
            <p class="text-gray-500 leading-relaxed text-sm">{service.get("description", "")}</p>
          </div>
        </div>""")
    return f"""
  <section id="services" class="py-24 md:py-32 bg-white">
    <div class="max-w-3xl mx-auto px-6">
      <div class="text-center mb-16" data-aos="fade-up">
        <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color: var(--accent);">Lo que ofrecemos</div>
        <h2 class="text-3xl md:text-4xl font-bold text-gray-900">Nuestros Servicios</h2>
      </div>
      <div>
        {"".join(items)}
      </div>
    </div>
  </section>
"""


def build_services_featured(services: list, accent: str) -> str:
    """Services variant 3: First service featured large, rest in 2-col grid."""
    accent_bg = hex_to_rgba(accent, 0.12)
    if not services:
        return ""
    first = services[0]
    first_icon = ICONS[0]
    featured = f"""
      <div class="service-card bg-white rounded-2xl p-10 md:p-12 shadow-sm border border-gray-100 mb-10" data-aos="fade-up">
        <div class="flex flex-col md:flex-row items-start gap-6">
          <div class="w-16 h-16 rounded-2xl flex items-center justify-center flex-shrink-0" style="background-color: {accent_bg}; color: {accent};">
            {first_icon}
          </div>
          <div>
            <h3 class="text-2xl font-bold text-gray-900 mb-4">{first.get("headline", first.get("name", ""))}</h3>
            <p class="text-gray-500 leading-relaxed text-base">{first.get("description", "")}</p>
          </div>
        </div>
      </div>"""
    rest_cards = []
    for i, service in enumerate(services[1:], 1):
        icon = ICONS[i % len(ICONS)]
        delay = i * 100
        rest_cards.append(f"""
        <div class="service-card bg-white rounded-2xl p-8 shadow-sm border border-gray-100 group" data-aos="fade-up" data-aos-delay="{delay}">
          <div class="w-12 h-12 rounded-xl flex items-center justify-center mb-6" style="background-color: {accent_bg}; color: {accent};">
            {icon}
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-3">{service.get("headline", service.get("name", ""))}</h3>
          <p class="text-gray-500 leading-relaxed text-sm">{service.get("description", "")}</p>
        </div>""")
    return f"""
  <section id="services" class="py-24 md:py-32 bg-white">
    <div class="max-w-6xl mx-auto px-6">
      <div class="text-center mb-16" data-aos="fade-up">
        <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color: var(--accent);">Lo que ofrecemos</div>
        <h2 class="text-3xl md:text-4xl font-bold text-gray-900">Nuestros Servicios</h2>
      </div>
      {featured}
      <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
        {"".join(rest_cards)}
      </div>
    </div>
  </section>
"""


# ---------------------------------------------------------------------------
# Main HTML assembly — composable, multi-axis
# ---------------------------------------------------------------------------

def build_html(business_info: dict, website_copy: dict, hero_video_url: str = None, hero_video_poster: str = None, animation_palette: list = None, preview_only: bool = False) -> str:
    name = business_info.get("business_name", "Business Name")
    tagline = business_info.get("tagline", "")
    contact = business_info.get("contact", {})
    social_links = business_info.get("social_links", {})
    colors = business_info.get("color_scheme", {})
    brand = business_info.get("brand", {})
    google_places = business_info.get("google_places")
    hero_image_path = business_info.get("hero_image_path")

    # --- Colors ---
    primary = brand.get("primary_color") or colors.get("primary", "#1e3a5f")
    secondary = colors.get("secondary", "#f5f7fa")
    accent = colors.get("accent", "#c9a84c")
    palette = generate_color_palette(primary)
    primary_dark = palette.get(700, darken_color(primary))
    primary_text = get_text_color_for_bg(primary)
    secondary_text = get_text_color_for_bg(secondary)

    palette_css_lines = ""
    if palette:
        palette_css_lines = "\n" + "\n".join(
            f"      --primary-{shade}: {color};"
            for shade, color in sorted(palette.items())
        )

    # --- Multi-axis variant selection ---
    axes = compute_variant_axes(name)
    font_id = axes["font_id"]
    layout_id = axes["layout_id"]
    hero_id = axes["hero_id"]
    services_id = axes["services_id"]
    personality_id = axes["personality_id"]

    # Allow business_info to override personality if set by gather_business_info (legacy)
    personality_override = business_info.get("personality")
    if personality_override:
        override_map = {"minimal": 0, "bold": 1, "warm": 2, "corporate": 3, "modern": 4}
        personality_id = override_map.get(personality_override.lower(), personality_id)

    # Apply design_hints from gather_business_info (reasoning-based, overrides hash for all axes)
    design_hints = business_info.get("design_hints", {})
    if design_hints:
        _font_map = {"classic": 0, "editorial": 1, "refined": 2, "geometric": 3, "warm": 4}
        _hero_map = {"centered": 0, "left-aligned": 1, "diagonal": 2, "split": 3}
        _personality_map = {"minimal": 0, "bold": 1, "warm": 2, "corporate": 3, "modern": 4}
        _layout_map = {"classic": 0, "story-first": 1, "services-focused": 2, "minimal": 3}
        fh = design_hints.get("font_pairing", "")
        hh = design_hints.get("hero_layout", "")
        ph = design_hints.get("visual_personality", "")
        lh = design_hints.get("page_layout", "")
        if fh: font_id = _font_map.get(fh.lower(), font_id)
        if hh: hero_id = _hero_map.get(hh.lower(), hero_id)
        if ph: personality_id = _personality_map.get(ph.lower(), personality_id)
        if lh: layout_id = _layout_map.get(lh.lower(), layout_id)

    fonts = FONT_PAIRINGS[font_id]
    font_url = fonts["url"]
    font_heading = fonts["heading"]
    font_body = fonts["body"]
    personality_css = PERSONALITY_CSS[personality_id]
    layout_order = LAYOUT_ORDERS[layout_id]

    # --- Copy sections ---
    hero = website_copy.get("hero", {})
    about = website_copy.get("about", {})
    services = website_copy.get("services", [])
    social_proof = website_copy.get("social_proof", {})
    cta_section = website_copy.get("cta_section", {})
    footer = website_copy.get("footer", {})
    faq = website_copy.get("faq", [])
    seo = website_copy.get("seo", {})
    testimonials = website_copy.get("testimonials", [])

    # --- SEO ---
    seo_title = html_lib.escape(seo.get("title") or name)
    seo_description = html_lib.escape(seo.get("meta_description", ""))

    # --- Build section HTML blocks ---
    reviews_html = build_reviews_html(google_places, accent) if google_places else ""
    faq_html = build_faq_html(faq, accent)
    schema_html = build_schema_org(business_info, website_copy)
    trust_html = build_trust_badges_html(business_info, accent)
    emergency_html = build_emergency_bar(contact.get("phone", ""))
    testimonials_html = build_testimonials_html(testimonials, accent)
    contact_info_html = build_contact_info_html(contact, accent)
    social_html = build_social_html(social_links or {}, accent)
    about_paragraphs_html = build_about_paragraphs(about.get("paragraphs", []), "var(--primary-text)")
    stats_html = build_stats_html(social_proof.get("stats", []), accent)

    real_rating_stat = ""
    if google_places and google_places.get("rating"):
        real_rating_stat = f"""
        <div class="text-center px-8">
          <div class="text-5xl font-extrabold mb-3" style="color: {accent};">{google_places["rating"]}</div>
          <div class="text-gray-300 text-sm uppercase tracking-widest font-medium">Valoraci&oacute;n en Google</div>
        </div>"""

    # --- Hero variant ---
    hero_builders = [build_hero_centered, build_hero_left, build_hero_diagonal, build_hero_split]
    if hero_id == 3:
        hero_html = build_hero_split(hero, tagline, name, primary, hero_video_url, hero_video_poster, hero_image_path)
    else:
        hero_html = hero_builders[hero_id](hero, tagline, hero_video_url, hero_video_poster, hero_image_path)

    # --- Services variant ---
    services_builders = [build_services_grid, build_services_alternating, build_services_list, build_services_featured]
    services_section_html = services_builders[services_id](services, accent)

    # --- About section ---
    about_section_html = f"""
  <section id="about" class="py-24 md:py-32" style="background: var(--primary);">
    <div class="max-w-6xl mx-auto px-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
        <div data-aos="fade-right">
          <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color: var(--accent);">{about.get("section_title", "Qui&eacute;nes Somos")}</div>
          <h2 class="text-3xl md:text-4xl font-bold mb-8" style="color: var(--primary-text);">Qui&eacute;nes Somos</h2>
          {about_paragraphs_html}
          <a href="#contact" class="btn-primary mt-8 inline-block">{hero.get("cta_primary", "Cont&aacute;ctanos")}</a>
        </div>
        <div class="relative" data-aos="fade-left">
          <div class="rounded-3xl p-12 flex items-center justify-center min-h-80" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15);">
            <div class="text-center text-white">
              <svg class="w-20 h-20 mx-auto mb-5 opacity-30" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
              </svg>
              <p class="text-2xl font-bold mb-2" style="color: var(--primary-text);">{html_lib.escape(name)}</p>
              <p class="text-sm font-medium" style="color: var(--primary-text); opacity: 0.6;">{html_lib.escape(tagline)}</p>
            </div>
          </div>
          <div class="absolute -bottom-4 -right-4 w-24 h-24 rounded-2xl -z-10" style="background-color: var(--accent); opacity: 0.25;"></div>
        </div>
      </div>
    </div>
  </section>
"""

    # --- About brief (for minimal layout) ---
    about_brief_html = f"""
  <section id="about" class="py-16 md:py-24" style="background-color: var(--secondary);">
    <div class="max-w-3xl mx-auto px-6 text-center" data-aos="fade-up">
      <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color: var(--accent);">{about.get("section_title", "Qui&eacute;nes Somos")}</div>
      <h2 class="text-3xl md:text-4xl font-bold mb-6" style="color: var(--secondary-text);">Qui&eacute;nes Somos</h2>
      <p class="leading-relaxed text-lg" style="color: var(--secondary-text); opacity: 0.8;">{(about.get("paragraphs", [""])[0])}</p>
    </div>
  </section>
"""

    # --- Stats section ---
    stats_section_html = f"""
  <section class="py-20 md:py-28 hero-bg">
    <div class="max-w-6xl mx-auto px-6">
      <div class="text-center mb-14" data-aos="fade-up">
        <h2 class="text-2xl md:text-3xl font-bold mb-4" style="color: var(--primary-text);">{social_proof.get("section_title", "Nuestros Resultados")}</h2>
        <p class="max-w-2xl mx-auto leading-relaxed" style="color: var(--primary-text); opacity: 0.82;">{social_proof.get("statement", "")}</p>
      </div>
      <div class="flex flex-col sm:flex-row items-center justify-center gap-0 divide-y sm:divide-y-0 sm:divide-x divide-white divide-opacity-15">
        {real_rating_stat}
        {stats_html}
      </div>
    </div>
  </section>
"""

    # --- Stats+CTA combined (for layout 1) ---
    submit_btn_text = html_lib.escape(cta_section.get("button_text", "Enviar Mensaje"))
    stats_cta_html = f"""
  <section class="py-20 md:py-28 hero-bg">
    <div class="max-w-6xl mx-auto px-6">
      <div class="text-center mb-14" data-aos="fade-up">
        <h2 class="text-2xl md:text-3xl font-bold mb-4" style="color: var(--primary-text);">{social_proof.get("section_title", "Nuestros Resultados")}</h2>
      </div>
      <div class="flex flex-col sm:flex-row items-center justify-center gap-0 divide-y sm:divide-y-0 sm:divide-x divide-white divide-opacity-15 mb-14">
        {real_rating_stat}
        {stats_html}
      </div>
      <div class="text-center" data-aos="fade-up">
        <h3 class="text-2xl md:text-3xl font-bold mb-4" style="color: var(--primary-text);">{cta_section.get("headline", "&iquest;Listo para empezar?")}</h3>
        <p class="mb-8 leading-relaxed" style="color: var(--primary-text); opacity: 0.82;">{cta_section.get("subtext", "")}</p>
        <a href="#contact" class="btn-primary text-base">{submit_btn_text}</a>
      </div>
    </div>
  </section>
"""

    # --- CTA banner ---
    cta_section_html = f"""
  <section class="py-20 md:py-28 bg-white">
    <div class="max-w-3xl mx-auto px-6 text-center" data-aos="fade-up">
      <h2 class="text-3xl md:text-4xl font-bold text-gray-900 mb-4">{cta_section.get("headline", "&iquest;Listo para empezar?")}</h2>
      <p class="text-gray-500 text-lg mb-10 leading-relaxed">{cta_section.get("subtext", "")}</p>
      <a href="#contact" class="btn-primary text-base">{submit_btn_text}</a>
    </div>
  </section>
"""

    # --- Contact section ---
    formspree_endpoint = os.getenv("FORMSPREE_ENDPOINT", "")
    contact_section_html = f"""
  <section id="contact" class="py-24 md:py-32" style="background-color: var(--secondary);">
    <div class="max-w-6xl mx-auto px-6">
      <div class="text-center mb-16" data-aos="fade-up">
        <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color: var(--accent);">Ponte en Contacto</div>
        <h2 class="text-3xl md:text-4xl font-bold" style="color: var(--secondary-text);">Cont&aacute;ctanos</h2>
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-16">
        <div data-aos="fade-right">
          <p class="leading-relaxed mb-10" style="color: var(--secondary-text); opacity: 0.75;">
            Estaremos encantados de atenderte. Escr&iacute;benos o cont&aacute;ctanos por cualquiera de los canales a continuaci&oacute;n.
          </p>
          <div class="space-y-6">
            {contact_info_html}
          </div>
        </div>
        <div class="bg-white rounded-2xl p-8 shadow-sm border border-gray-100" data-aos="fade-left">
          <h3 class="text-xl font-semibold text-gray-900 mb-6">Env&iacute;anos un Mensaje</h3>
          <form id="contact-form" class="space-y-4" onsubmit="handleFormSubmit(event)">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <input type="text" name="nombre" placeholder="Nombre" class="form-input" required>
              <input type="text" name="apellido" placeholder="Apellido" class="form-input" required>
            </div>
            <input type="email" name="email" placeholder="Correo electr&oacute;nico" class="form-input" required>
            <input type="tel" name="telefono" placeholder="Tel&eacute;fono (opcional)" class="form-input">
            <textarea name="mensaje" rows="4" placeholder="&iquest;C&oacute;mo podemos ayudarte?" class="form-input resize-none" required></textarea>
            <button type="submit" class="btn-primary w-full text-center">
              {submit_btn_text}
            </button>
            <div id="form-success" class="hidden text-center py-3 px-4 bg-green-50 text-green-700 rounded-lg text-sm font-medium">
              &#10003; &iexcl;Mensaje enviado! Nos pondremos en contacto pronto.
            </div>
            <div id="form-error" class="hidden text-center py-3 px-4 bg-red-50 text-red-600 rounded-lg text-sm font-medium">
              &#10007; Error al enviar. Por favor, int&eacute;ntalo de nuevo.
            </div>
          </form>
        </div>
      </div>
    </div>
  </section>
"""

    # --- Nav ---
    logo_local_path = brand.get("logo_local_path")
    if logo_local_path:
        nav_logo_html = f'<a href="#"><img src="{logo_local_path}" alt="{html_lib.escape(name)} logo" class="h-10 w-auto object-contain"></a>'
    else:
        nav_logo_html = f'<a href="#" class="text-xl font-bold tracking-tight" style="color: var(--primary);">{html_lib.escape(name)}</a>'

    nav_html = f"""
  <nav class="nav-bar">
    <div class="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
      {nav_logo_html}
      <div class="hidden md:flex items-center gap-8">
        <a href="#services" class="text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors">Servicios</a>
        <a href="#about" class="text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors">Nosotros</a>
        <a href="#contact" class="text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors">Contacto</a>
        <a href="#contact" class="btn-primary !py-2.5 !px-5 !text-sm">{hero.get("cta_primary", "Cont&aacute;ctanos")}</a>
      </div>
      <button
        class="md:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
        onclick="const m = document.getElementById('mobile-nav'); m.classList.toggle('hidden');"
        aria-label="Abrir men&uacute;"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
      </button>
    </div>
    <div id="mobile-nav" class="hidden md:hidden border-t border-gray-100 px-6 py-4 space-y-3">
      <a href="#services" class="block text-sm font-medium text-gray-700 py-1.5">Servicios</a>
      <a href="#about" class="block text-sm font-medium text-gray-700 py-1.5">Nosotros</a>
      <a href="#contact" class="block text-sm font-medium text-gray-700 py-1.5">Contacto</a>
      <a href="#contact" class="btn-primary block text-center mt-4 !text-sm">{hero.get("cta_primary", "Cont&aacute;ctanos")}</a>
    </div>
  </nav>
"""

    # --- Footer ---
    footer_html = f"""
  <footer class="hero-bg py-12">
    <div class="max-w-6xl mx-auto px-6">
      <div class="flex flex-col md:flex-row items-center justify-between gap-6 pb-8 border-b border-white border-opacity-10">
        <div>
          <div class="text-xl font-bold mb-1" style="color: var(--primary-text);">{html_lib.escape(name)}</div>
          <div class="text-sm font-medium" style="color: var(--primary-text); opacity: 0.65;">{html_lib.escape(footer.get("tagline", tagline))}</div>
        </div>
        <nav class="flex gap-6">
          <a href="#services" class="text-sm font-medium transition-opacity hover:opacity-100" style="color: var(--primary-text); opacity: 0.75;">Servicios</a>
          <a href="#about" class="text-sm font-medium transition-opacity hover:opacity-100" style="color: var(--primary-text); opacity: 0.75;">Nosotros</a>
          <a href="#contact" class="text-sm font-medium transition-opacity hover:opacity-100" style="color: var(--primary-text); opacity: 0.75;">Contacto</a>
        </nav>
        {social_html}
      </div>
      <div class="pt-6 text-center text-xs" style="color: var(--primary-text); opacity: 0.45;">
        &copy; 2026 {html_lib.escape(name)}. Todos los derechos reservados.
      </div>
    </div>
  </footer>
"""

    # --- Assemble page by layout order ---
    section_map = {
        "hero": hero_html,
        "trust": trust_html,
        "services": services_section_html,
        "reviews": reviews_html,
        "testimonials": testimonials_html,
        "about": about_section_html,
        "about_brief": about_brief_html,
        "stats": stats_section_html,
        "stats_cta": stats_cta_html,
        "cta": cta_section_html,
        "faq": faq_html,
        "contact": contact_section_html,
    }

    body_sections = []
    active_sections = ["hero"] if preview_only else layout_order
    for section_key in active_sections:
        html_block = section_map.get(section_key, "")
        if html_block:
            body_sections.append(html_block)

    # --- Animation scripts (palette-driven) ---
    _palette = animation_palette or _DEFAULT_PALETTE
    animation_scripts = generate_animation_scripts(_palette, accent)

    # --- Assemble full HTML ---
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{seo_title}</title>
  <meta name="description" content="{seo_description}">
  <meta property="og:title" content="{seo_title}">
  <meta property="og:description" content="{seo_description}">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="es_ES">
  <meta name="twitter:card" content="summary_large_image">
  {schema_html}
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="{font_url}" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{ font-family: {font_body}; -webkit-font-smoothing: antialiased; }}
    h1, h2, h3, h4 {{ font-family: {font_heading}; }}

    :root {{
      --primary: {primary};
      --primary-dark: {primary_dark};
      --primary-text: {primary_text};
      --secondary: {secondary};
      --secondary-text: {secondary_text};
      --accent: {accent};
      --font-heading: {font_heading};
      --font-body: {font_body};{palette_css_lines}
    }}

    .btn-primary {{
      display: inline-block;
      background-color: var(--accent);
      color: #fff;
      font-weight: 600;
      font-size: 0.9375rem;
      padding: 0.875rem 2rem;
      border-radius: 0.5rem;
      text-decoration: none;
      transition: opacity 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
    }}
    .btn-primary:hover {{
      opacity: 0.92;
      transform: translateY(-2px);
      box-shadow: 0 12px 30px {hex_to_rgba(accent, 0.35)};
    }}

    .btn-outline {{
      display: inline-block;
      border: 2px solid rgba(255,255,255,0.6);
      color: #fff;
      font-weight: 600;
      font-size: 0.9375rem;
      padding: calc(0.875rem - 2px) calc(2rem - 2px);
      border-radius: 0.5rem;
      text-decoration: none;
      transition: background-color 0.15s ease, border-color 0.15s ease;
    }}
    .btn-outline:hover {{
      background-color: rgba(255,255,255,0.12);
      border-color: rgba(255,255,255,0.9);
    }}

    .nav-bar {{
      position: sticky;
      top: 0;
      z-index: 50;
      background-color: rgba(255,255,255,0.96);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-bottom: 1px solid rgba(0,0,0,0.06);
    }}

    .hero-bg {{
      background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
    }}

    .dot-pattern {{
      background-image: radial-gradient(circle, rgba(255,255,255,0.08) 1px, transparent 1px);
      background-size: 32px 32px;
    }}

    .form-input {{
      width: 100%;
      padding: 0.75rem 1rem;
      border: 1.5px solid #e5e7eb;
      border-radius: 0.5rem;
      font-size: 0.875rem;
      font-family: inherit;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
      outline: none;
    }}
    .form-input:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 3px {hex_to_rgba(accent, 0.12)};
    }}
    .form-input::placeholder {{ color: #9ca3af; }}

    .service-card {{
      transition: transform 0.25s ease, box-shadow 0.25s ease;
    }}
    .service-card:hover {{
      transform: translateY(-6px);
      box-shadow: 0 20px 40px rgba(0,0,0,0.12);
    }}
    .review-card {{
      transition: transform 0.25s ease, box-shadow 0.25s ease;
    }}
    .review-card:hover {{
      transform: translateY(-4px);
      box-shadow: 0 12px 28px rgba(0,0,0,0.10);
    }}
    .hero-video {{
      z-index: 0;
    }}
    .hero-video-overlay {{
      background: linear-gradient(to bottom, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.3) 40%, rgba(0,0,0,0.3) 60%, rgba(0,0,0,0.6) 100%);
      z-index: 1;
    }}

    @media (prefers-reduced-motion: reduce) {{
      .hero-video {{
        animation-play-state: paused !important;
      }}
    }}

    {personality_css}
  </style>
  <link rel="stylesheet" href="https://unpkg.com/aos@2.3.1/dist/aos.css">
</head>

<body class="text-gray-800 bg-white">

  {nav_html}

  {"".join(body_sections)}

  {footer_html}

  {emergency_html}

  <script>
    document.querySelectorAll('#mobile-nav a').forEach(link => {{
      link.addEventListener('click', () => {{
        document.getElementById('mobile-nav').classList.add('hidden');
      }});
    }});

    function toggleFaq(btn) {{
      const answer = btn.nextElementSibling;
      const icon = btn.querySelector('.faq-icon');
      const isOpen = !answer.classList.contains('hidden');
      document.querySelectorAll('.faq-answer').forEach(a => a.classList.add('hidden'));
      document.querySelectorAll('.faq-icon').forEach(i => {{ i.style.transform = ''; }});
      document.querySelectorAll('.faq-item button').forEach(b => b.setAttribute('aria-expanded', 'false'));
      if (!isOpen) {{
        answer.classList.remove('hidden');
        icon.style.transform = 'rotate(180deg)';
        btn.setAttribute('aria-expanded', 'true');
      }}
    }}

    function handleFormSubmit(e) {{
      e.preventDefault();
      const form = e.target;
      const btn = form.querySelector('button[type="submit"]');
      const successEl = document.getElementById('form-success');
      const errorEl = document.getElementById('form-error');
      btn.disabled = true;
      btn.textContent = 'Enviando\u2026';
      const endpoint = "{formspree_endpoint}";
      if (endpoint) {{
        fetch(endpoint, {{
          method: 'POST',
          body: new FormData(form),
          headers: {{ 'Accept': 'application/json' }}
        }})
        .then(r => {{
          if (r.ok) {{
            form.style.display = 'none';
            successEl.classList.remove('hidden');
          }} else {{
            btn.disabled = false;
            btn.textContent = '{submit_btn_text}';
            errorEl.classList.remove('hidden');
            setTimeout(() => errorEl.classList.add('hidden'), 5000);
          }}
        }})
        .catch(() => {{
          btn.disabled = false;
          btn.textContent = '{submit_btn_text}';
          errorEl.classList.remove('hidden');
          setTimeout(() => errorEl.classList.add('hidden'), 5000);
        }});
      }} else {{
        setTimeout(() => {{
          form.style.display = 'none';
          successEl.classList.remove('hidden');
        }}, 800);
      }}
    }}
  </script>
  <!-- cifra:animations:start -->
  {animation_scripts}
  <!-- cifra:animations:end -->
  <script>
  document.addEventListener('DOMContentLoaded', function() {{
    var v = document.querySelector('.hero-video');
    if (v) v.play().catch(function(){{}});
  }});
  </script>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Security seal injection (Pro tier and above)
# ---------------------------------------------------------------------------

_SECURITY_SEAL_HTML = """
<div style="display:flex;align-items:center;gap:10px;margin-top:16px;
            padding:10px 16px;background:rgba(193,122,58,0.1);
            border:1px solid rgba(193,122,58,0.3);border-radius:6px;
            width:fit-content;">
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
       stroke="#C17A3A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    <polyline points="9 12 11 14 15 10"/>
  </svg>
  <span style="font-size:11px;color:#C17A3A;font-weight:600;letter-spacing:0.05em;">
    AUDITORÍA DE SEGURIDAD INCLUIDA
  </span>
</div>
"""


def inject_security_seal(html_path: Path) -> None:
    """Insert the security audit seal badge before the closing </footer> tag."""
    try:
        source = html_path.read_text(encoding="utf-8")
        if "AUDITORÍA DE SEGURIDAD" in source:
            return  # Already injected
        source = source.replace("</footer>", _SECURITY_SEAL_HTML + "\n</footer>", 1)
        html_path.write_text(source, encoding="utf-8")
    except Exception as e:
        print(f"[WARN] Could not inject security seal: {e}")


def run_pre_launch_audit(output_path: Path, client_slug: str) -> Path | None:
    """Run security_audit.py in pre_launch mode on the generated HTML bundle."""
    audit_script = Path(__file__).parent / "security_audit.py"
    if not audit_script.exists():
        print("[WARN] security_audit.py not found — skipping pre-launch audit.")
        return None

    print(f"\n[SECURITY] Running pre-launch audit on {output_path} ...")
    result = subprocess.run(
        [sys.executable, str(audit_script),
         "--target", str(output_path),
         "--client-slug", client_slug,
         "--scan-mode", "pre_launch",
         "--skip-contract"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        findings_path = Path("output") / "audits" / client_slug / "findings.json"
        print(f"[SECURITY] Pre-launch audit complete. Findings: {findings_path}")
        return findings_path if findings_path.exists() else None
    else:
        print(f"[WARN] Pre-launch audit failed:\n{result.stderr[:500]}")
        return None


# ---------------------------------------------------------------------------
# Animation archetype scripts
# ---------------------------------------------------------------------------

def generate_animation_scripts(palette: list[str], accent: str = "#C17A3A") -> str:
    """
    Return <script> blocks for the selected animation archetypes.
    AOS is always included as baseline. Palette archetypes are additive.
    """
    scripts = []

    # Always: AOS
    scripts.append('<script src="https://unpkg.com/aos@2.3.1/dist/aos.js"></script>')
    scripts.append('<script>AOS.init({ duration: 700, once: true, offset: 60, easing: "ease-out-cubic" });</script>')

    # cursor_aura — radial gradient that follows mouse in hero
    if "cursor_aura" in palette:
        scripts.append(f"""<script>
(function() {{
  var hero = document.querySelector('.hero-section, section[id="hero"], .hero-bg');
  if (!hero) return;
  var aura = document.createElement('div');
  aura.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:2;transition:background 0.12s ease;border-radius:inherit;';
  if (getComputedStyle(hero).position === 'static') hero.style.position = 'relative';
  hero.appendChild(aura);
  hero.addEventListener('mousemove', function(e) {{
    var r = hero.getBoundingClientRect();
    var x = ((e.clientX - r.left) / r.width * 100).toFixed(1);
    var y = ((e.clientY - r.top) / r.height * 100).toFixed(1);
    aura.style.background = 'radial-gradient(600px circle at ' + x + '% ' + y + '%, {hex_to_rgba(accent, 0.18)} 0%, transparent 70%)';
  }});
  hero.addEventListener('mouseleave', function() {{ aura.style.background = 'none'; }});
}})();
</script>""")

    # marquee — continuous horizontal scroll strip
    if "marquee" in palette:
        scripts.append("""<script>
(function() {
  document.querySelectorAll('.marquee-track').forEach(function(track) {
    var clone = track.innerHTML;
    track.innerHTML += clone;
  });
})();
</script>""")

    # clip_path_reveal — headings clip in from right on scroll
    if "clip_path_reveal" in palette:
        scripts.append("""<script>
(function() {
  var els = document.querySelectorAll('.clip-reveal');
  if (!els.length) return;
  var io = new IntersectionObserver(function(entries) {
    entries.forEach(function(e) {
      if (e.isIntersecting) {
        e.target.style.clipPath = 'inset(0 0% 0 0)';
        e.target.style.opacity = '1';
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.15 });
  els.forEach(function(el) {
    el.style.clipPath = 'inset(0 100% 0 0)';
    el.style.opacity = '0';
    el.style.transition = 'clip-path 0.9s cubic-bezier(0,1,0.5,1), opacity 0.3s ease';
    io.observe(el);
  });
})();
</script>""")

    # grid_entrance — staggered card entrance
    if "grid_entrance" in palette:
        scripts.append("""<script>
(function() {
  var cards = document.querySelectorAll('.service-card, .feature-card, .grid-card');
  if (!cards.length) return;
  cards.forEach(function(card) {
    card.style.opacity = '0';
    card.style.transform = 'translateY(36px)';
    card.style.transition = 'none';
  });
  var io = new IntersectionObserver(function(entries) {
    entries.forEach(function(e) {
      if (e.isIntersecting) {
        var idx = parseInt(e.target.dataset.index || 0, 10);
        setTimeout(function() {
          e.target.style.transition = 'opacity 0.55s ease, transform 0.55s cubic-bezier(0.34,1.56,0.64,1)';
          e.target.style.opacity = '1';
          e.target.style.transform = 'translateY(0)';
        }, idx * 80);
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.1 });
  cards.forEach(function(card) { io.observe(card); });
})();
</script>""")

    # magnetic_button — CTAs pulled toward cursor
    if "magnetic_button" in palette:
        scripts.append("""<script>
(function() {
  document.querySelectorAll('.btn-primary, .btn-outline').forEach(function(btn) {
    btn.addEventListener('mousemove', function(e) {
      var r = btn.getBoundingClientRect();
      var dx = (e.clientX - (r.left + r.width / 2)) * 0.28;
      var dy = (e.clientY - (r.top + r.height / 2)) * 0.28;
      btn.style.transform = 'translate(' + dx + 'px,' + dy + 'px) scale(1.04)';
    });
    btn.addEventListener('mouseleave', function() {
      btn.style.transform = '';
    });
  });
})();
</script>""")

    # slow_parallax — background layers drift on scroll
    if "slow_parallax" in palette:
        scripts.append("""<script>
(function() {
  var layers = document.querySelectorAll('.parallax-layer');
  if (!layers.length) return;
  window.addEventListener('scroll', function() {
    var sy = window.scrollY;
    layers.forEach(function(l) {
      var factor = parseFloat(l.dataset.parallax || 0.25);
      l.style.transform = 'translateY(' + (sy * factor) + 'px)';
    });
  }, { passive: true });
})();
</script>""")

    # fade_up_stagger — replaces generic AOS on grouped items
    if "fade_up_stagger" in palette:
        scripts.append("""<script>
(function() {
  var groups = document.querySelectorAll('.stagger-group');
  groups.forEach(function(group) {
    var children = group.children;
    Array.from(children).forEach(function(child, i) {
      child.style.opacity = '0';
      child.style.transform = 'translateY(20px)';
      child.style.transition = 'none';
    });
    var io = new IntersectionObserver(function(entries) {
      if (entries[0].isIntersecting) {
        Array.from(children).forEach(function(child, i) {
          setTimeout(function() {
            child.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            child.style.opacity = '1';
            child.style.transform = 'translateY(0)';
          }, i * 80);
        });
        io.disconnect();
      }
    }, { threshold: 0.1 });
    io.observe(group);
  });
})();
</script>""")

    # 3d_tilt — card tilt on mousemove
    if "3d_tilt" in palette:
        scripts.append("""<script>
(function() {
  document.querySelectorAll('.tilt-card').forEach(function(card) {
    card.style.transition = 'transform 0.1s ease';
    card.addEventListener('mousemove', function(e) {
      var r = card.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width - 0.5;
      var y = (e.clientY - r.top) / r.height - 0.5;
      card.style.transform = 'perspective(900px) rotateY(' + (x * 12) + 'deg) rotateX(' + (-y * 12) + 'deg) scale(1.02)';
      var spec = card.querySelector('.specular');
      if (spec) spec.style.opacity = String(Math.abs(x) + Math.abs(y));
    });
    card.addEventListener('mouseleave', function() {
      card.style.transform = 'perspective(900px) rotateY(0deg) rotateX(0deg) scale(1)';
      var spec = card.querySelector('.specular');
      if (spec) spec.style.opacity = '0';
    });
  });
})();
</script>""")

    # stat_counter — RAF lerp for numeric stats
    if "stat_counter" in palette:
        scripts.append("""<script>
(function() {
  var counters = document.querySelectorAll('.counter[data-target]');
  if (!counters.length) return;
  var io = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (!entry.isIntersecting) return;
      var el = entry.target;
      var target = parseFloat(el.dataset.target);
      var suffix = el.dataset.suffix || '';
      var decimals = (el.dataset.target.indexOf('.') !== -1) ? 1 : 0;
      var current = 0;
      var start = null;
      var duration = 1800;
      function step(ts) {
        if (!start) start = ts;
        var progress = Math.min((ts - start) / duration, 1);
        var ease = 1 - Math.pow(1 - progress, 3);
        current = target * ease;
        el.textContent = current.toFixed(decimals) + suffix;
        if (progress < 1) requestAnimationFrame(step);
        else el.textContent = target.toFixed(decimals) + suffix;
      }
      requestAnimationFrame(step);
      io.unobserve(el);
    });
  }, { threshold: 0.5 });
  counters.forEach(function(c) { io.observe(c); });
})();
</script>""")

    # spring_hover — always included (lightweight CSS-only, no extra JS needed beyond reminder)
    # Handled via .btn-primary CSS already; no extra script needed.

    return "\n  ".join(scripts)


# ---------------------------------------------------------------------------
# Dead CTA validator
# ---------------------------------------------------------------------------

def validate_no_dead_ctas(html: str) -> str:
    """
    Strip any <a> or <button> that has href='#' but isn't a logo/scroll-top link.
    Replaces dead 'Ver más'-type anchors with their text content (no link).
    Logs a warning for each removal.
    """
    dead_patterns = [
        r'<a\s[^>]*href=["\']#["\'][^>]*>\s*(?:Ver m[áa]s|M[áa]s informaci[óo]n|Ver detalles|Saber m[áa]s|Descubrir m[áa]s)\s*</a>',
    ]
    for pattern in dead_patterns:
        matches = re.findall(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        for m in matches:
            text_content = re.sub(r'<[^>]+>', '', m).strip()
            print(f"[WARN] Removed dead CTA: '{text_content}' (no destination)")
            html = html.replace(m, f'<span class="text-sm font-medium" style="opacity:0.6">{text_content}</span>')
    return html


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_DEMO_PALETTES = {
    "minimal":   ["slow_parallax", "fade_up_stagger", "magnetic_button"],
    "bold":      ["marquee", "spring_hover", "grid_entrance"],
    "warm":      ["fade_up_stagger", "3d_tilt", "stat_counter"],
    "corporate": ["clip_path_reveal", "fade_up_stagger", "stat_counter"],
    "modern":    ["cursor_aura", "clip_path_reveal", "spring_hover"],
}

_DEFAULT_PALETTE = ["fade_up_stagger", "stat_counter", "spring_hover"]

# Tier-gated animation palettes for the --polish pass
_TIER_PALETTES = {
    "starter": ["fade_up_stagger", "stat_counter"],
    "basic":   ["fade_up_stagger", "stat_counter"],
    "pro":     ["fade_up_stagger", "stat_counter", "3d_tilt", "slow_parallax", "spring_hover"],
    "enterprise": ["cursor_aura", "fade_up_stagger", "stat_counter", "3d_tilt", "slow_parallax", "spring_hover", "clip_path_reveal", "magnetic_button"],
}


def main():
    parser = argparse.ArgumentParser(description="Build business website HTML")
    parser.add_argument("--brief", default=None, help="Path to design_brief.json (Client Mode)")
    parser.add_argument("--preview", action="store_true", help="Build hero-only preview page -> output/hero_preview.html")
    parser.add_argument("--polish", action="store_true", help="Upgrade animation tier in existing output/index.html")
    parser.add_argument("--tier", default=None, choices=["starter", "basic", "pro", "enterprise"], help="Client tier (used with --polish)")
    args = parser.parse_args()

    info_path = Path(".tmp/business_info.json")
    copy_path = Path(".tmp/website_copy.json")

    if not info_path.exists():
        print("Error: .tmp/business_info.json not found.")
        print("Run Step 1 first: python tools/gather_business_info.py \"your description\"")
        sys.exit(1)

    if not copy_path.exists():
        print("Error: .tmp/website_copy.json not found.")
        print("Run Step 2 first: python tools/generate_copy.py")
        sys.exit(1)

    with open(info_path, encoding="utf-8") as f:
        business_info = json.load(f)

    with open(copy_path, encoding="utf-8") as f:
        website_copy = json.load(f)

    # Determine animation palette: brief > design_hints personality > default
    design_brief = {}
    if args.brief:
        brief_path = Path(args.brief)
        if brief_path.exists():
            with open(brief_path, encoding="utf-8") as f:
                design_brief = json.load(f)
            print(f"[BRIEF] Loaded: {brief_path} (mode={design_brief.get('mode','?')}, emotion={design_brief.get('emotional_target','?')})")
        else:
            print(f"[WARN] Brief file not found: {brief_path} — falling back to demo mode")

    animation_palette = design_brief.get("animation_palette") or None
    if not animation_palette:
        personality = (business_info.get("design_hints", {}).get("visual_personality") or "").lower()
        animation_palette = _DEMO_PALETTES.get(personality, _DEFAULT_PALETTE)

    biz_name = business_info.get("business_name", "Unknown")
    axes = compute_variant_axes(biz_name)
    # Apply design_hints for accurate print output (mirrors logic in build_html)
    _dh = business_info.get("design_hints", {})
    if _dh:
        _fm = {"classic": 0, "editorial": 1, "refined": 2, "geometric": 3, "warm": 4}
        _hm = {"centered": 0, "left-aligned": 1, "diagonal": 2, "split": 3}
        _pm = {"minimal": 0, "bold": 1, "warm": 2, "corporate": 3, "modern": 4}
        _lm = {"classic": 0, "story-first": 1, "services-focused": 2, "minimal": 3}
        if _dh.get("font_pairing"): axes["font_id"] = _fm.get(_dh["font_pairing"].lower(), axes["font_id"])
        if _dh.get("hero_layout"): axes["hero_id"] = _hm.get(_dh["hero_layout"].lower(), axes["hero_id"])
        if _dh.get("visual_personality"): axes["personality_id"] = _pm.get(_dh["visual_personality"].lower(), axes["personality_id"])
        if _dh.get("page_layout"): axes["layout_id"] = _lm.get(_dh["page_layout"].lower(), axes["layout_id"])
    source = "brief" if design_brief else ("design_hints" if _dh else "hash")

    # -------------------------------------------------------------------------
    # --polish: upgrade animation tier in existing output/index.html
    # -------------------------------------------------------------------------
    if args.polish:
        site_path = Path("output/index.html")
        if not site_path.exists():
            print("Error: output/index.html not found — run a full build first.")
            sys.exit(1)
        tier = args.tier or business_info.get("tier", "starter")
        polish_palette = _TIER_PALETTES.get(tier, _DEFAULT_PALETTE)
        accent = (
            business_info.get("brand", {}).get("accent_color")
            or business_info.get("color_scheme", {}).get("accent", "#C17A3A")
        )
        new_scripts = generate_animation_scripts(polish_palette, accent)
        html = site_path.read_text(encoding="utf-8")
        import re as _re
        pattern = r'<!-- cifra:animations:start -->.*?<!-- cifra:animations:end -->'
        replacement = f'<!-- cifra:animations:start -->\n  {new_scripts}\n  <!-- cifra:animations:end -->'
        if _re.search(pattern, html, flags=_re.DOTALL):
            html = _re.sub(pattern, replacement, html, flags=_re.DOTALL)
            site_path.write_text(html, encoding="utf-8")
            print(f"[POLISH] Animation tier '{tier}' injected → {site_path}")
            print(f"  Palette: {', '.join(polish_palette)}")
        else:
            print("[WARN] Animation markers not found — site may have been built before multi-pass support.")
            print("       Rebuild with: python tools/build_website.py")
        return

    # -------------------------------------------------------------------------
    # --preview: hero-only preview page → output/hero_preview.html
    # -------------------------------------------------------------------------
    if args.preview:
        print(f"[PREVIEW] Building hero preview for: {biz_name}")
        html = build_html(
            business_info, website_copy,
            hero_video_url=business_info.get("hero_video_url"),
            hero_video_poster=business_info.get("hero_video_poster"),
            animation_palette=animation_palette,
            preview_only=True,
        )
        Path("output").mkdir(exist_ok=True)
        preview_path = Path("output/hero_preview.html")
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[OK] Hero preview saved to {preview_path}")
        print(f"  Hero: \"{website_copy.get('hero', {}).get('headline', 'N/A')}\"")
        print("\n[GATE] Review hero_preview.html, then run:")
        print("       python tools/generate_copy.py --pass 2")
        return

    print(f"Building website for: {biz_name}")
    print(f"  Font     : {FONT_PAIRINGS[axes['font_id']]['label']} ({FONT_PAIRINGS[axes['font_id']]['heading']}) [{source}]")
    print(f"  Layout   : {axes['layout_id']} / Hero: {axes['hero_id']} / Services: {axes['services_id']} [{source}]")
    print(f"  Style    : {PERSONALITY_LABELS[axes['personality_id']]} [{source}]")
    print(f"  Animations: {', '.join(animation_palette)}")

    html = build_html(
        business_info, website_copy,
        hero_video_url=business_info.get("hero_video_url"),
        hero_video_poster=business_info.get("hero_video_poster"),
        animation_palette=animation_palette,
    )
    html = validate_no_dead_ctas(html)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "index.html"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = round(len(html.encode("utf-8")) / 1024, 1)
    brand = business_info.get("brand", {})
    gp = business_info.get("google_places")
    active_primary = brand.get("primary_color") or business_info.get("color_scheme", {}).get("primary")

    print(f"\n[OK] Website saved to {output_path} ({size_kb} KB)")

    sections = f"Nav, Hero(v{axes['hero_id']}), Services(v{axes['services_id']})"
    if gp and gp.get("reviews"):
        sections += f", Reviews ({len(gp['reviews'])})"
    if website_copy.get("testimonials"):
        sections += f", Testimonials ({len(website_copy['testimonials'])})"
    sections += ", About, Stats, CTA"
    if website_copy.get("faq"):
        sections += f", FAQ ({len(website_copy['faq'])} Q&As)"
    sections += ", Contact, Footer"
    print(f"  Sections : {sections}")
    print(f"  Colors   : primary={active_primary}  accent={business_info.get('color_scheme', {}).get('accent')}")
    if website_copy.get("seo", {}).get("title"):
        print(f"  SEO title: \"{website_copy['seo']['title']}\"")
    if brand.get("source"):
        print(f"  Brand    : logo={brand.get('logo_local_path', 'none')}  source={brand['source']}")
    if business_info.get("hero_image_path"):
        print(f"  Hero img : {business_info['hero_image_path']}")

    # --- Pre-launch security audit (Pro tier and above) ---
    tier = business_info.get("tier", "basic")
    client_slug = business_info.get("slug") or re.sub(r"[^a-z0-9]+", "-", biz_name.lower()).strip("-")

    if tier in ("pro", "premium", "enterprise"):
        findings_path = run_pre_launch_audit(output_path, client_slug)
        inject_security_seal(output_path)
        print(f"  Tier     : {tier} — security seal injected into footer")

        # Log audit to DB if available
        if findings_path and findings_path.exists():
            try:
                sys.path.insert(0, str(Path(__file__).parent))
                from db import add_audit, get_client
                client = get_client(client_slug)
                if client:
                    with open(findings_path, encoding="utf-8") as fh:
                        findings_data = json.load(fh)
                    summary = findings_data.get("summary", {})
                    add_audit(
                        client_slug=client_slug,
                        scan_type="website_build",
                        findings_json_path=str(findings_path),
                        total_findings=summary.get("total", 0),
                        high=summary.get("high", 0),
                        medium=summary.get("medium", 0),
                        low=summary.get("low", 0),
                    )
            except Exception as e:
                print(f"  [WARN] Could not log audit to DB: {e}")


if __name__ == "__main__":
    main()
