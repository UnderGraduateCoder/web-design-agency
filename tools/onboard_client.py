"""
onboard_client.py

Usage:
    python tools/onboard_client.py --lead-id 42 [--tier basic|pro|premium|enterprise] [--live]

One-command client onboarding. Performs all of:
    1. Creates client record in DB (via create_client_from_lead)
    2. Generates service contract PDF from templates/service_contract_template_es.md
    3. Generates security authorization contract PDF (via pdf_engine)
    4. Creates workspace folders: brand_assets/{slug}/ + output/{websites,audits,quotes}/{slug}/
    5. Sends welcome email with both contracts attached + Calendly link
       - dry_run=True by default (use --live to send real emails)
    6. Logs contract_sent_at in DB
    7. Marks lead as 'won'

Requires: ANTHROPIC_API_KEY, RESEND_API_KEY or SMTP_*, CALENDLY_URL in .env
"""

import sys
import io
import os
import re
import argparse
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.db import get_lead, create_client_from_lead, update_lead_status, log_contract_sent, init_db

TIER_PRICING = {
    "basic":      {"one_time": 690,  "monthly": 49,  "label": "Basic"},
    "pro":        {"one_time": 1290, "monthly": 89,  "label": "Pro"},
    "premium":    {"one_time": 1990, "monthly": 129, "label": "Premium"},
    "enterprise": {"one_time": 3500, "monthly": 199, "label": "Enterprise"},
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _interpolate(template: str, data: dict) -> str:
    for key, value in data.items():
        template = template.replace(f"[{key}]", str(value))
    return template


def _build_contract_html(markdown_content: str, title: str) -> str:
    """Wrap interpolated markdown content in styled HTML for PDF generation."""
    lines = markdown_content.split("\n")
    body = ""
    for line in lines:
        if line.startswith("# "):
            body += f'<h1 style="font-family:\'Playfair Display\',serif;color:#1A1410;font-size:24px;margin-bottom:16px;">{line[2:]}</h1>\n'
        elif line.startswith("## "):
            body += f'<h2 style="font-family:\'Playfair Display\',serif;color:#1A1410;font-size:17px;margin:20px 0 8px;border-bottom:1px solid #C17A3A;padding-bottom:4px;">{line[3:]}</h2>\n'
        elif line.startswith("### "):
            body += f'<h3 style="color:#3E2E1E;font-size:14px;margin:14px 0 6px;">{line[4:]}</h3>\n'
        elif line.startswith("- ") or line.startswith("* "):
            body += f'<li style="margin-bottom:4px;color:#3E2E1E;font-size:12px;">{line[2:]}</li>\n'
        elif line.strip() == "---":
            body += '<hr style="border:none;border-top:1px solid #E8DBC0;margin:16px 0;">\n'
        elif line.strip():
            body += f'<p style="font-size:12px;color:#3E2E1E;line-height:1.7;margin-bottom:8px;">{line}</p>\n'
        else:
            body += "<br>\n"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Plus+Jakarta+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>
  @page {{ size: A4; margin: 20mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Plus Jakarta Sans', sans-serif; color: #1A1410; background: #fff; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  td, th {{ padding: 8px 12px; border: 1px solid #E8DBC0; font-size: 12px; }}
  th {{ background: #1A1410; color: #F5EDD6; text-align: left; }}
  strong {{ color: #1A1410; }}
</style>
</head>
<body>
<div style="background:#1A1410;padding:20px 24px;margin:-20mm -20mm 24px;">
  <p style="font-family:'Playfair Display',serif;font-size:20px;color:#C17A3A;font-weight:700;margin:0;">URDIMBRE</p>
  <p style="font-size:11px;color:#8A5225;margin:4px 0 0;letter-spacing:.08em;text-transform:uppercase;">{title}</p>
</div>
{body}
</body>
</html>"""


def _write_pdf(html_content: str, out_path: Path) -> Path:
    """Write HTML → PDF via pdf_engine (WeasyPrint → Playwright → html fallback)."""
    import sys as _sys
    _root = str(Path(__file__).parent.parent)
    if _root not in _sys.path:
        _sys.path.insert(0, _root)
    from tools.pdf_engine import render_pdf
    return render_pdf(html_content, out_path)


def _generate_service_contract(lead: dict, slug: str, tier: str, date_str: str) -> Path:
    template_path = Path("templates/service_contract_template_es.md")
    if not template_path.exists():
        raise FileNotFoundError("templates/service_contract_template_es.md not found")

    template = template_path.read_text(encoding="utf-8")
    pricing = TIER_PRICING[tier]

    data = {
        "NOMBRE COMPLETO": lead.get("email", "").split("@")[0].title() or "[Nombre]",
        "CARGO EN LA EMPRESA": "Representante legal",
        "NOMBRE DE LA EMPRESA": lead["business_name"],
        "CIF/NIF DE LA EMPRESA": "[CIF/NIF]",
        "DIRECCIÓN COMPLETA": lead.get("region", "[Dirección]"),
        "EMAIL DE CONTACTO": lead.get("email", "[Email]"),
        "TELÉFONO DE CONTACTO": lead.get("phone", "[Teléfono]"),
        "PLAN": pricing["label"],
        "PRECIO INICIAL": f"{pricing['one_time']} €",
        "CUOTA MENSUAL": f"{pricing['monthly']} €/mes",
        "FECHA": date_str,
        "YYYY": datetime.now().strftime("%Y"),
        "NNN": "001",
        "DD/MM/YYYY": date_str,
    }

    filled = _interpolate(template, data)
    html = _build_contract_html(filled, "Contrato de Servicios")

    out_dir = Path(f"brand_assets/{slug}")
    out_dir.mkdir(parents=True, exist_ok=True)
    date_file = datetime.now().strftime("%Y-%m-%d")
    return _write_pdf(html, out_dir / f"service_contract_{date_file}.pdf")


def _generate_auth_contract(lead: dict, slug: str, date_str: str) -> Path:
    template_path = Path("templates/authorization_contract_template.md")
    if not template_path.exists():
        raise FileNotFoundError("templates/authorization_contract_template.md not found")

    template = template_path.read_text(encoding="utf-8")

    data = {
        "NOMBRE COMPLETO": lead.get("email", "").split("@")[0].title() or "[Nombre]",
        "CARGO EN LA EMPRESA": "Representante legal",
        "NOMBRE DE LA EMPRESA": lead["business_name"],
        "CIF/NIF DE LA EMPRESA": "[CIF/NIF]",
        "DIRECCIÓN COMPLETA": lead.get("region", "[Dirección]"),
        "EMAIL DE CONTACTO": lead.get("email", "[Email]"),
        "TELÉFONO DE CONTACTO": lead.get("phone", "[Teléfono]"),
        "FECHA": date_str,
        "YYYY": datetime.now().strftime("%Y"),
        "NNN": "001",
        "DD/MM/YYYY": date_str,
    }

    filled = _interpolate(template, data)
    html = _build_contract_html(filled, "Autorización de Seguridad")

    out_dir = Path(f"brand_assets/{slug}")
    out_dir.mkdir(parents=True, exist_ok=True)
    date_file = datetime.now().strftime("%Y-%m-%d")
    return _write_pdf(html, out_dir / f"authorization_contract_{date_file}.pdf")


def _create_folders(slug: str) -> list[Path]:
    folders = [
        Path(f"brand_assets/{slug}"),
        Path(f"output/websites/{slug}"),
        Path(f"output/audits/{slug}"),
        Path(f"output/quotes/{slug}"),
    ]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
    return folders


def _welcome_email_html(lead: dict, tier: str, calendly_url: str) -> str:
    pricing = TIER_PRICING[tier]
    name = lead["business_name"]
    return f"""
<div style="font-family:Georgia,serif;font-size:15px;line-height:1.8;color:#1A1410;max-width:600px;">
  <p style="font-family:'Plus Jakarta Sans',sans-serif;font-size:20px;color:#C17A3A;font-weight:700;margin-bottom:4px;">URDIMBRE</p>
  <hr style="border:none;border-top:1px solid #E8DBC0;margin-bottom:24px;">

  <p>Bienvenido/a a Cifra, {name}.</p>

  <p>Es un placer comenzar a trabajar juntos. Adjunto encontrará:</p>
  <ul style="margin:12px 0;padding-left:24px;">
    <li>Contrato de servicios — plan <strong>{pricing['label']}</strong></li>
    <li>Autorización de seguridad</li>
  </ul>

  <p>Por favor, revise los documentos y responda a este correo con su firma (puede imprimirlos, firmarlos y fotografiarlos, o usar una firma electrónica).</p>

  <p>El proyecto comenzará en <strong>48 horas</strong> desde la recepción de los contratos firmados.</p>

  <p>Para coordinar la llamada de descubrimiento, puede reservar directamente aquí:<br>
  <a href="{calendly_url}" style="color:#C17A3A;">{calendly_url}</a></p>

  <p style="margin-top:24px;">Un saludo,<br>
  <strong>Adrián</strong><br>
  <span style="color:#8A5225;font-size:13px;">Cifra · adrianarconroyo@gmail.com</span></p>
</div>"""


def run(lead_id: int, tier: str, live: bool = False) -> None:
    init_db()  # ensure contract_sent_at column exists
    lead = get_lead(lead_id)
    if not lead:
        print(f"[ERROR] Lead {lead_id} not found.")
        sys.exit(1)

    name = lead["business_name"]
    slug = _slug(name)
    date_str = datetime.now().strftime("%d/%m/%Y")
    dry_run = not live

    print(f"\n[Onboarding] {name} (lead #{lead_id}) | Tier: {tier} | mode={'LIVE' if live else 'DRY RUN'}")

    # Step 1 — Create client in DB
    print("\n  [1/7] Creating client in DB...")
    client_id = None
    try:
        client_id = create_client_from_lead(lead_id, tier)
        print(f"  Client ID: {client_id}")
    except Exception as e:
        print(f"  [WARN] DB insert failed (may already exist): {e}")
        # Retrieve existing client id
        try:
            from tools.db import get_client
            existing = get_client(slug)
            if existing:
                client_id = existing["id"]
                print(f"  Existing client ID: {client_id}")
        except Exception:
            pass

    # Step 2 — Service contract PDF
    print("  [2/7] Generating service contract PDF...")
    service_pdf = _generate_service_contract(lead, slug, tier, date_str)
    print(f"  → {service_pdf}")

    # Step 3 — Auth contract PDF
    print("  [3/7] Generating authorization contract PDF...")
    auth_pdf = _generate_auth_contract(lead, slug, date_str)
    print(f"  → {auth_pdf}")

    # Step 4 — Create folders
    print("  [4/7] Creating workspace folders...")
    folders = _create_folders(slug)
    for f in folders:
        print(f"  → {f}/")

    # Step 5 — Send welcome email
    calendly_url = os.getenv("CALENDLY_URL", "https://calendly.com/cifra")
    print(f"  [5/7] {'Sending' if live else 'Dry-run'} welcome email to {lead.get('email', '[no email]')}...")

    attachments = [str(p) for p in [service_pdf, auth_pdf] if Path(p).suffix == ".pdf" and Path(p).exists()]
    if not lead.get("email"):
        print("  [WARN] No email address — skipping welcome email")
    else:
        from tools.email_sender import send_email
        send_email(
            to=lead["email"],
            subject="Bienvenido a Cifra — Contratos y próximos pasos",
            body_html=_welcome_email_html(lead, tier, calendly_url),
            attachments=attachments if attachments else None,
            dry_run=dry_run,
        )
        if dry_run:
            print(f"  [DRY RUN] Would send to {lead['email']} with {len(attachments)} attachment(s): {attachments}")
        else:
            print("  Email sent.")

    # Step 6 — Log contract_sent_at in DB
    print("  [6/7] Logging contract delivery in DB...")
    if client_id:
        try:
            log_contract_sent(client_id)
            print(f"  contract_sent_at recorded for client #{client_id}")
        except Exception as e:
            print(f"  [WARN] Could not log contract_sent_at: {e}")
    else:
        print("  [SKIP] client_id not available, skipping DB log")

    # Step 7 — Mark as won
    print("  [7/7] Marking lead as 'won'...")
    update_lead_status(lead_id, "won")

    print(f"\n[DONE] {name} onboarded successfully.")
    print(f"  Client slug  : {slug}")
    print(f"  Tier         : {TIER_PRICING[tier]['label']}")
    print(f"  Lead status  : won")
    print(f"  Contracts    : brand_assets/{slug}/")
    print(f"  Email mode   : {'LIVE' if live else 'DRY RUN (pass --live to send real emails)'}")
    print(f"  Workspace    : output/websites/{slug}/, output/audits/{slug}/, output/quotes/{slug}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Onboard a won lead as a client")
    parser.add_argument("--lead-id", type=int, required=True)
    parser.add_argument("--tier", default="basic", choices=list(TIER_PRICING.keys()))
    parser.add_argument("--live", action="store_true", help="Send real emails (default: dry-run)")
    args = parser.parse_args()
    run(args.lead_id, args.tier, live=args.live)
