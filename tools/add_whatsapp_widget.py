import sys
import re
import argparse
from pathlib import Path
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
import db

INJECT_MARKER = 'data-wat-whatsapp="1"'


def _extract_primary_color(html: str) -> str:
    """Extract primary brand color from :root CSS custom properties."""
    root_match = re.search(r':root\s*\{([^}]+)\}', html, re.DOTALL)
    if not root_match:
        return "#25D366"

    block = root_match.group(1)

    # Preference order: --primary, --copper, first hex color in vars
    for pattern in [r'--primary\s*:\s*(#[0-9a-fA-F]{6})', r'--copper\s*:\s*(#[0-9a-fA-F]{6})']:
        m = re.search(pattern, block)
        if m:
            return m.group(1)

    m = re.search(r'--[\w-]+\s*:\s*(#[0-9a-fA-F]{6})', block)
    if m:
        return m.group(1)

    return "#25D366"


def _strip_phone(phone: str) -> str:
    """Return digits only (no +) for wa.me URL."""
    return re.sub(r'[^\d]', '', phone)


def _build_widget_html(phone: str, message: str, hours: str, position: str, brand_color: str) -> str:
    phone_digits = _strip_phone(phone)
    encoded_msg = quote_plus(message)
    side = "right: 24px;" if position == "bottom-right" else "left: 24px;"
    tooltip_side = "right: 24px;" if position == "bottom-right" else "left: 24px;"

    # Lighten brand color for box-shadow glow (append 55 for 33% opacity)
    glow = brand_color + "55"

    return f"""
  <!-- WAT WhatsApp Widget -->
  <style>
    .wat-wa-wrap {{ position: fixed; bottom: 24px; {side} z-index: 9999; display: flex; flex-direction: column; align-items: flex-end; }}
    .wat-wa-btn {{
      width: 56px; height: 56px; border-radius: 50%;
      background: {brand_color};
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 4px 16px {glow};
      cursor: pointer; text-decoration: none;
      transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.2s ease;
    }}
    .wat-wa-btn:hover {{ transform: scale(1.1); box-shadow: 0 6px 24px {glow}; }}
    .wat-wa-btn svg {{ width: 28px; height: 28px; fill: white; }}
    .wat-wa-tooltip {{
      margin-bottom: 8px;
      background: white; border-radius: 8px;
      padding: 8px 12px; font-size: 13px; color: #333;
      box-shadow: 0 2px 12px rgba(0,0,0,0.12);
      opacity: 0; pointer-events: none;
      transition: opacity 0.2s ease;
      white-space: nowrap; max-width: 240px;
      font-family: system-ui, sans-serif;
    }}
    .wat-wa-wrap:hover .wat-wa-tooltip {{ opacity: 1; }}
  </style>
  <div class="wat-wa-wrap">
    <div class="wat-wa-tooltip">{hours}</div>
    <a
      data-wat-whatsapp="1"
      class="wat-wa-btn"
      href="https://wa.me/{phone_digits}?text={encoded_msg}"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Contactar por WhatsApp"
    >
      <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
      </svg>
    </a>
  </div>
  <!-- /WAT WhatsApp Widget -->"""


def _activate_service(slug: str) -> None:
    """Mark whatsapp_widget as active in client_services, inserting if needed."""
    with db._connect() as conn:
        row = conn.execute("SELECT id FROM clients WHERE slug=?", (slug,)).fetchone()
        if not row:
            return
        client_id = row["id"]
        existing = conn.execute(
            "SELECT id FROM client_services WHERE client_id=? AND service_code='whatsapp_widget'",
            (client_id,),
        ).fetchone()
        if existing:
            conn.execute("UPDATE client_services SET active=1 WHERE id=?", (existing["id"],))
        else:
            conn.execute(
                "INSERT INTO client_services(client_id, service_code, active) VALUES(?,?,1)",
                (client_id, "whatsapp_widget"),
            )


def main():
    parser = argparse.ArgumentParser(description="Inject WhatsApp widget into a client website")
    parser.add_argument("--client-slug", required=True)
    parser.add_argument("--phone", required=True, help="WhatsApp Business number, E.164 format")
    parser.add_argument("--message", required=True, help="Pre-filled welcome message (Spanish)")
    parser.add_argument("--hours", required=True, help="Business hours for tooltip")
    parser.add_argument("--position", default="bottom-right", choices=["bottom-right", "bottom-left"])
    args = parser.parse_args()

    slug = args.client_slug
    print(f"[whatsapp-integration] Client: {slug}")

    # Step 1 — Validate client
    client = db.get_client(slug)
    if not client:
        print(f"Error: Client '{slug}' not found in database.")
        sys.exit(1)

    # Step 2 — Read website
    index_path = Path("output/websites") / slug / "index.html"
    if not index_path.exists():
        print(f"Error: {index_path} not found. Build the website first.")
        sys.exit(1)

    html = index_path.read_text(encoding="utf-8")

    # Step 3 — Extract brand color
    brand_color = _extract_primary_color(html)
    print(f"  Brand color: {brand_color}")

    # Step 4 — Idempotency check
    if INJECT_MARKER in html:
        print("  [SKIP] WhatsApp widget already present — no changes made.")
        sys.exit(0)

    # Step 5 — Build widget
    widget_html = _build_widget_html(args.phone, args.message, args.hours, args.position, brand_color)

    # Step 6 — Inject before </body>
    if "</body>" not in html:
        print("Error: </body> tag not found in index.html")
        sys.exit(1)

    modified = html.replace("</body>", widget_html + "\n</body>", 1)
    index_path.write_text(modified, encoding="utf-8")
    print(f"  Injected widget into {index_path}")

    # Step 7 — Log service activation
    _activate_service(slug)
    print(f"  Service 'whatsapp_widget' activated in DB")
    print(f"[whatsapp-integration] Done — widget at {args.position}, phone {args.phone}")


if __name__ == "__main__":
    main()
