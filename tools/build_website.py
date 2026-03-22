"""
build_website.py

Usage:
    python tools/build_website.py

Reads .tmp/business_info.json and .tmp/website_copy.json, then generates
a self-contained, responsive output/index.html using Tailwind CSS (CDN)
and Google Fonts. No build step required.

Run gather_business_info.py and generate_copy.py first.
"""

import sys
import json
import os
import re
import colorsys
import html as html_lib
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
# Industry variant system
# ---------------------------------------------------------------------------

VARIANT_KEYWORDS = {
    "professional": [
        "law", "legal", "abogad", "accounting", "contab", "consulting",
        "medical", "dental", "insurance", "financial", "notari", "asesor",
    ],
    "trade": [
        "hvac", "plumb", "fontaner", "electric", "roofing", "construction",
        "construcc", "security", "landscaping", "jardin", "pest", "painting",
        "carpinter", "cerrajer", "alarm", "instalac",
    ],
    "food": [
        "restaurant", "restaurante", "cafe", "café", "bakery", "panaderi",
        "catering", "cocina", "food", "comida",
    ],
    "tech": [
        "software", "tech", "tecnolog", "marketing", "digital", "photography",
        "fotograf", "design", "diseño", "agencia", "web", "app",
    ],
    "wellness": [
        "fitness", "gym", "gimnas", "yoga", "spa", "beauty", "belleza",
        "salon", "peluquer", "massage", "childcare", "pet", "mascota", "veterinar",
    ],
}


def detect_variant(industry: str) -> str:
    """Return the design variant that best matches the given industry string."""
    industry_lower = industry.lower()
    for variant, keywords in VARIANT_KEYWORDS.items():
        if any(kw in industry_lower for kw in keywords):
            return variant
    return "professional"


VARIANT_FONTS = {
    "professional": {
        "url": "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Lato:wght@300;400;500;600;700&display=swap",
        "heading": "'Playfair Display', serif",
        "body": "'Lato', sans-serif",
    },
    "trade": {
        "url": "https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Open+Sans:wght@400;500;600;700&display=swap",
        "heading": "'Oswald', sans-serif",
        "body": "'Open Sans', sans-serif",
    },
    "food": {
        "url": "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Lato:wght@300;400;500;600;700&display=swap",
        "heading": "'Playfair Display', serif",
        "body": "'Lato', sans-serif",
    },
    "tech": {
        "url": "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap",
        "heading": "'Space Grotesk', sans-serif",
        "body": "'Inter', sans-serif",
    },
    "wellness": {
        "url": "https://fonts.googleapis.com/css2?family=Nunito:wght@600;700;800&family=Poppins:wght@300;400;500;600&display=swap",
        "heading": "'Nunito', sans-serif",
        "body": "'Poppins', sans-serif",
    },
}

# Raw CSS strings — NOT f-strings. The { } here are literal CSS braces.
VARIANT_CSS = {
    "professional": """
    /* Professional — elegant, serif, trust */
    h1, h2, h3 { letter-spacing: -0.02em; }
    .btn-primary { border-radius: 0.375rem; letter-spacing: 0.01em; }
    .service-card { border-radius: 1rem; }""",

    "trade": """
    /* Trade — bold, high-contrast, action-oriented */
    h1, h2, h3 { text-transform: uppercase; letter-spacing: 0.04em; }
    .hero-bg { background: linear-gradient(180deg, var(--primary) 0%, var(--primary-900) 100%); }
    .btn-primary { border-radius: 0.25rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; }
    .service-card { border-left: 4px solid var(--accent); border-radius: 0.5rem; }""",

    "food": """
    /* Food — warm, rounded, editorial */
    h1, h2, h3 { letter-spacing: -0.01em; }
    .service-card { border-radius: 1.5rem; }
    .btn-primary { border-radius: 9999px; }
    .review-card { border-radius: 1.5rem; }""",

    "tech": """
    /* Tech — glassmorphism, dark hero, modern */
    h1, h2, h3 { letter-spacing: -0.03em; }
    .hero-bg { background: linear-gradient(135deg, #0f0f1a 0%, var(--primary) 60%, var(--primary-dark) 100%); }
    .service-card { background: linear-gradient(145deg, #ffffff 0%, #f8faff 100%); border-radius: 1rem; }""",

    "wellness": """
    /* Wellness — soft, rounded, calming */
    h1, h2, h3 { font-weight: 700; }
    .hero-bg { background: linear-gradient(160deg, var(--primary-700) 0%, var(--primary) 100%); }
    .service-card { border-radius: 1.5rem; box-shadow: 0 4px 20px rgba(0,0,0,0.06); }
    .btn-primary { border-radius: 9999px; }
    .review-card { border-radius: 1.5rem; }""",
}


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
# HTML section builders
# ---------------------------------------------------------------------------

def build_services_html(services: list, accent: str) -> str:
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
    return "\n".join(cards)


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
    """Return True if phone appears to be a Spanish mobile number (6xx or 7xx).
    WhatsApp only works with mobile numbers — never use it for landlines (9xx).
    """
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
        # IMPORTANT: Never invent or fill in review text.
        # Only render the quote paragraph when real text exists.
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
  <!-- ============================================================
       GOOGLE REVIEWS
  ============================================================ -->
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


def build_trust_badges(variant: str, accent: str) -> str:
    """Render a trust bar below the nav (Professional variant only)."""
    if variant != "professional":
        return ""
    shield = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>'
    lock = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>'
    clock = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
    badges = [
        (shield, "Colegiado y Certificado"),
        (lock, "Confidencialidad Total"),
        (clock, "+15 A&ntilde;os de Experiencia"),
    ]
    items = "".join(
        f'<div class="flex items-center gap-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">'
        f'<span style="color:{accent};">{svg}</span>{label}</div>'
        for svg, label in badges
    )
    return f"""
  <!-- Trust Badges (Professional variant) -->
  <div class="bg-gray-50 border-b border-gray-100 py-2.5">
    <div class="max-w-6xl mx-auto px-6 flex items-center justify-center gap-8 flex-wrap">
      {items}
    </div>
  </div>
"""


def build_emergency_bar(phone: str, variant: str) -> str:
    """Render a sticky 'Call Now' bar at the bottom on mobile (Trade variant only)."""
    if variant != "trade" or not phone:
        return ""
    phone_svg = '<svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>'
    return f"""
  <!-- Emergency Call Bar (Trade — sticky mobile bottom) -->
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
  <!-- ============================================================
       FAQ
  ============================================================ -->
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
    """Generate Schema.org LocalBusiness JSON-LD. Uses json.dumps to safely escape all strings."""
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
  <!-- ============================================================
       TESTIMONIALS (synthesized from real reviews)
  ============================================================ -->
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
# Main HTML assembly
# ---------------------------------------------------------------------------

def build_html(business_info: dict, website_copy: dict) -> str:
    name = business_info.get("business_name", "Business Name")
    tagline = business_info.get("tagline", "")
    contact = business_info.get("contact", {})
    social_links = business_info.get("social_links", {})
    colors = business_info.get("color_scheme", {})
    brand = business_info.get("brand", {})
    google_places = business_info.get("google_places")
    industry = business_info.get("industry", "")
    hero_image_path = business_info.get("hero_image_path")

    # --- Colors ---
    primary = brand.get("primary_color") or colors.get("primary", "#1e3a5f")
    secondary = colors.get("secondary", "#f5f7fa")
    accent = colors.get("accent", "#c9a84c")
    palette = generate_color_palette(primary)
    primary_dark = palette.get(700, darken_color(primary))
    primary_text = get_text_color_for_bg(primary)
    secondary_text = get_text_color_for_bg(secondary)

    # Palette CSS custom properties for :root
    palette_css_lines = ""
    if palette:
        palette_css_lines = "\n" + "\n".join(
            f"      --primary-{shade}: {color};"
            for shade, color in sorted(palette.items())
        )

    # --- Variant ---
    variant = detect_variant(industry)
    fonts = VARIANT_FONTS[variant]
    font_url = fonts["url"]
    font_heading = fonts["heading"]
    font_body = fonts["body"]
    variant_css = VARIANT_CSS[variant]

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

    # --- Build HTML blocks ---
    services_html = build_services_html(services, accent)
    stats_html = build_stats_html(social_proof.get("stats", []), accent)
    contact_info_html = build_contact_info_html(contact, accent)
    social_html = build_social_html(social_links or {}, accent)
    about_paragraphs_html = build_about_paragraphs(about.get("paragraphs", []), "var(--primary-text)")
    reviews_html = build_reviews_html(google_places, accent) if google_places else ""
    faq_html = build_faq_html(faq, accent)
    schema_html = build_schema_org(business_info, website_copy)
    trust_badges_html = build_trust_badges(variant, accent)
    emergency_bar_html = build_emergency_bar(contact.get("phone", ""), variant)
    testimonials_html = build_testimonials_html(testimonials, accent)

    # --- Layout helpers ---
    count = len(services)
    grid_cols = "lg:grid-cols-3" if count >= 3 else ("lg:grid-cols-2" if count == 2 else "lg:grid-cols-1")

    logo_local_path = brand.get("logo_local_path")
    if logo_local_path:
        nav_logo_html = f'<a href="#"><img src="{logo_local_path}" alt="{html_lib.escape(name)} logo" class="h-10 w-auto object-contain"></a>'
    else:
        nav_logo_html = f'<a href="#" class="text-xl font-bold tracking-tight" style="color: var(--primary);">{html_lib.escape(name)}</a>'

    if hero_image_path:
        hero_section_open = (
            f'<section class="relative overflow-hidden py-28 md:py-36" '
            f'style="background: url(\'{hero_image_path}\') center/cover no-repeat;">'
        )
        hero_overlay = '<div class="absolute inset-0" style="background: rgba(0,0,0,0.55);"></div>'
    else:
        hero_section_open = '<section class="hero-bg relative overflow-hidden py-28 md:py-36">'
        hero_overlay = '<div class="absolute inset-0 dot-pattern"></div>'

    real_rating_stat = ""
    if google_places and google_places.get("rating"):
        real_rating_stat = f"""
        <div class="text-center px-8">
          <div class="text-5xl font-extrabold mb-3" style="color: {accent};">{google_places["rating"]}</div>
          <div class="text-gray-300 text-sm uppercase tracking-widest font-medium">Valoraci&oacute;n en Google</div>
        </div>"""

    # --- Formspree ---
    formspree_endpoint = os.getenv("FORMSPREE_ENDPOINT", "")
    submit_btn_text = html_lib.escape(cta_section.get("button_text", "Enviar Mensaje"))

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
    {variant_css}
  </style>
  <link rel="stylesheet" href="https://unpkg.com/aos@2.3.1/dist/aos.css">
</head>

<body class="text-gray-800 bg-white">

  <!-- ============================================================
       NAVIGATION
  ============================================================ -->
  <nav class="nav-bar">
    <div class="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
      {nav_logo_html}

      <!-- Desktop nav -->
      <div class="hidden md:flex items-center gap-8">
        <a href="#services" class="text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors">Servicios</a>
        <a href="#about" class="text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors">Nosotros</a>
        <a href="#contact" class="text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors">Contacto</a>
        <a href="#contact" class="btn-primary !py-2.5 !px-5 !text-sm">{hero.get("cta_primary", "Cont&aacute;ctanos")}</a>
      </div>

      <!-- Mobile hamburger -->
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

    <!-- Mobile menu -->
    <div id="mobile-nav" class="hidden md:hidden border-t border-gray-100 px-6 py-4 space-y-3">
      <a href="#services" class="block text-sm font-medium text-gray-700 py-1.5">Servicios</a>
      <a href="#about" class="block text-sm font-medium text-gray-700 py-1.5">Nosotros</a>
      <a href="#contact" class="block text-sm font-medium text-gray-700 py-1.5">Contacto</a>
      <a href="#contact" class="btn-primary block text-center mt-4 !text-sm">{hero.get("cta_primary", "Cont&aacute;ctanos")}</a>
    </div>
  </nav>

  {trust_badges_html}

  <!-- ============================================================
       HERO
  ============================================================ -->
  {hero_section_open}
    {hero_overlay}
    <div class="relative max-w-5xl mx-auto px-6 text-center text-white">
      <div class="inline-flex items-center gap-2 bg-white bg-opacity-15 border border-white border-opacity-20 text-white text-xs font-semibold uppercase tracking-widest px-4 py-2 rounded-full mb-8">
        <span style="color: var(--accent);">&#9679;</span>
        {tagline}
      </div>
      <h1 class="text-4xl sm:text-5xl md:text-6xl font-extrabold leading-tight tracking-tight mb-6">
        {hero.get("headline", name)}
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


  <!-- ============================================================
       SERVICES
  ============================================================ -->
  <section id="services" class="py-24 md:py-32 bg-white">
    <div class="max-w-6xl mx-auto px-6">
      <div class="text-center mb-16" data-aos="fade-up">
        <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color: var(--accent);">Lo que ofrecemos</div>
        <h2 class="text-3xl md:text-4xl font-bold text-gray-900">Nuestros Servicios</h2>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 {grid_cols} gap-8">
        {services_html}
      </div>
    </div>
  </section>


  {reviews_html}

  {testimonials_html}

  <!-- ============================================================
       ABOUT
  ============================================================ -->
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


  <!-- ============================================================
       SOCIAL PROOF / STATS
  ============================================================ -->
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


  <!-- ============================================================
       CTA BANNER
  ============================================================ -->
  <section class="py-20 md:py-28 bg-white">
    <div class="max-w-3xl mx-auto px-6 text-center" data-aos="fade-up">
      <h2 class="text-3xl md:text-4xl font-bold text-gray-900 mb-4">{cta_section.get("headline", "&iquest;Listo para empezar?")}</h2>
      <p class="text-gray-500 text-lg mb-10 leading-relaxed">{cta_section.get("subtext", "")}</p>
      <a href="#contact" class="btn-primary text-base">{submit_btn_text}</a>
    </div>
  </section>


  {faq_html}

  <!-- ============================================================
       CONTACT
  ============================================================ -->
  <section id="contact" class="py-24 md:py-32" style="background-color: var(--secondary);">
    <div class="max-w-6xl mx-auto px-6">
      <div class="text-center mb-16" data-aos="fade-up">
        <div class="text-xs font-bold uppercase tracking-widest mb-3" style="color: var(--accent);">Ponte en Contacto</div>
        <h2 class="text-3xl md:text-4xl font-bold" style="color: var(--secondary-text);">Cont&aacute;ctanos</h2>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-16">

        <!-- Contact info -->
        <div data-aos="fade-right">
          <p class="leading-relaxed mb-10" style="color: var(--secondary-text); opacity: 0.75;">
            Estaremos encantados de atenderte. Escr&iacute;benos o cont&aacute;ctanos por cualquiera de los canales a continuaci&oacute;n.
          </p>
          <div class="space-y-6">
            {contact_info_html}
          </div>
        </div>

        <!-- Contact form -->
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


  <!-- ============================================================
       FOOTER
  ============================================================ -->
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

  {emergency_bar_html}

  <script>
    // Mobile nav: close on link click
    document.querySelectorAll('#mobile-nav a').forEach(link => {{
      link.addEventListener('click', () => {{
        document.getElementById('mobile-nav').classList.add('hidden');
      }});
    }});

    // FAQ accordion
    function toggleFaq(btn) {{
      const answer = btn.nextElementSibling;
      const icon = btn.querySelector('.faq-icon');
      const isOpen = !answer.classList.contains('hidden');
      // Close all
      document.querySelectorAll('.faq-answer').forEach(a => a.classList.add('hidden'));
      document.querySelectorAll('.faq-icon').forEach(i => {{ i.style.transform = ''; }});
      document.querySelectorAll('.faq-item button').forEach(b => b.setAttribute('aria-expanded', 'false'));
      // Open clicked if it was closed
      if (!isOpen) {{
        answer.classList.remove('hidden');
        icon.style.transform = 'rotate(180deg)';
        btn.setAttribute('aria-expanded', 'true');
      }}
    }}

    // Contact form — Formspree AJAX if endpoint set, fake submission otherwise
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
  <script src="https://unpkg.com/aos@2.3.1/dist/aos.js"></script>
  <script>AOS.init({{ duration: 700, once: true, offset: 60 }});</script>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
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

    biz_name = business_info.get("business_name")
    industry = business_info.get("industry", "")
    variant = detect_variant(industry)
    print(f"Building website for: {biz_name}")
    print(f"  Variant  : {variant} (industry: {industry})")

    html = build_html(business_info, website_copy)

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

    sections = f"Nav, Hero, Services ({len(website_copy.get('services', []))})"
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
    print(f"  Fonts    : {VARIANT_FONTS[variant]['heading']} / {VARIANT_FONTS[variant]['body']}")
    if website_copy.get("seo", {}).get("title"):
        print(f"  SEO title: \"{website_copy['seo']['title']}\"")
    if brand.get("source"):
        print(f"  Brand    : logo={brand.get('logo_local_path', 'none')}  source={brand['source']}")
    if business_info.get("hero_image_path"):
        print(f"  Hero img : {business_info['hero_image_path']}")
    if os.getenv("FORMSPREE_ENDPOINT"):
        print(f"  Forms    : Formspree AJAX active")
    print("\nOpen in browser:")
    print(f"  start {output_path}   (Windows)")
    print(f"  open  {output_path}   (macOS)")


if __name__ == "__main__":
    main()
