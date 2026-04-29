"""
generate_proposal_pdf.py

Usage:
    python tools/generate_proposal_pdf.py --lead-id 42 [--tier basic|pro|premium|enterprise]
    python tools/generate_proposal_pdf.py --brief "Restaurante en Madrid, sin web" [--tier pro]

Generates a commercial proposal PDF (Propuesta Comercial) in Spanish, using
the same Copper/Linen/Charcoal palette and WeasyPrint pipeline as the audit
and quote PDFs.

Output: output/proposals/{lead_slug}/proposal_{date}.pdf

Structure:
    1. Cover — client name, date, Cifra branding
    2. Situación actual — website status framed as business cost
    3. Tier propuesto — feature table comparing tiers
    4. Fases del proyecto — Discovery → Design → Build → Launch → Maintenance
    5. Inversión — pricing table one-time + monthly
    6. Casos de éxito — up to 3 screenshots from output/websites/
    7. Próximos pasos + signature block
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


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

TIER_PRICING = {
    "basic":      {"one_time": 690,  "monthly": 49,  "label": "Basic"},
    "pro":        {"one_time": 1290, "monthly": 89,  "label": "Pro"},
    "premium":    {"one_time": 1990, "monthly": 129, "label": "Premium"},
    "enterprise": {"one_time": 3500, "monthly": 199, "label": "Enterprise"},
}

TIER_FEATURES = {
    "basic":      ["Web de 1–3 páginas", "Diseño responsive", "Hosting básico", "SSL incluido", "Soporte por email"],
    "pro":        ["Web de hasta 6 páginas", "Diseño premium", "Hosting rápido", "Auditoría mensual", "Soporte prioritario", "Google Analytics"],
    "premium":    ["Web ilimitada", "Diseño Awwwards-level", "Hosting enterprise", "Auditoría semanal", "Gestor de contenidos", "Integración Google Ads"],
    "enterprise": ["Todo lo de Premium", "Desarrollo a medida", "SLA garantizado", "Consultor dedicado", "Integraciones avanzadas"],
}

SITE_STATUS_ANALYSIS = {
    "no_site": (
        "El negocio no cuenta con presencia web. Cada día sin sitio web supone clientes "
        "que buscan en Google y acaban en la competencia. Según Google, el 76% de los consumidores "
        "investiga online antes de visitar un negocio local."
    ),
    "broken": (
        "El sitio web actual no carga correctamente. Un site caído genera desconfianza inmediata "
        "y afecta directamente al posicionamiento en Google. Los usuarios que no pueden acceder "
        "a la web simplemente llaman al siguiente resultado."
    ),
    "outdated": (
        "El sitio web existe pero no está optimizado para móviles ni para los estándares actuales "
        "de Google. Más del 60% del tráfico local proviene de dispositivos móviles — un sitio "
        "desactualizado pierde esa audiencia por completo."
    ),
    "modern": (
        "El sitio web es funcional, pero existen oportunidades claras de mejora en velocidad de "
        "carga, posicionamiento SEO local y tasa de conversión que pueden incrementar significativamente "
        "el número de contactos generados."
    ),
}

PROJECT_PHASES = [
    ("Descubrimiento", "1 semana", "Análisis del negocio, competencia y objetivos. Definición de contenidos y arquitectura."),
    ("Diseño", "1–2 semanas", "Diseño visual personalizado, paleta de marca, tipografías y componentes UI."),
    ("Desarrollo", "1–2 semanas", "Maquetación responsive, animaciones, formularios e integración de herramientas."),
    ("Lanzamiento", "1–3 días", "Publicación del dominio, SSL, pruebas de velocidad y envío a Google Search Console."),
    ("Mantenimiento", "Mensual", "Hosting, backups, actualizaciones de seguridad y soporte continuo."),
]


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _tier_features_table(recommended: str) -> str:
    tiers = ["basic", "pro", "premium", "enterprise"]
    headers = "".join(
        f'<th style="background:{"#C17A3A" if t == recommended else "#2C2018"};color:#F5EDD6;'
        f'padding:10px 14px;font-family:\'Plus Jakarta Sans\',sans-serif;font-size:12px;'
        f'font-weight:600;text-transform:uppercase;letter-spacing:.08em;">'
        f'{TIER_PRICING[t]["label"]}</th>'
        for t in tiers
    )

    all_features = []
    for t in tiers:
        for f in TIER_FEATURES[t]:
            if f not in all_features:
                all_features.append(f)

    rows = ""
    for i, feat in enumerate(all_features):
        bg = "#F5EDD6" if i % 2 == 0 else "#E8DBC0"
        cells = ""
        for t in tiers:
            has = feat in TIER_FEATURES[t]
            mark = '<span style="color:#C17A3A;font-weight:700;">✓</span>' if has else '<span style="color:#aaa;">—</span>'
            cells += f'<td style="padding:8px 14px;text-align:center;background:{bg};">{mark}</td>'
        feat_cell = f'<td style="padding:8px 14px;background:{bg};color:#1A1410;font-size:13px;">{feat}</td>'
        rows += f"<tr>{feat_cell}{cells}</tr>"

    return f"""
<table style="width:100%;border-collapse:collapse;margin-top:12px;">
  <thead><tr><th style="padding:10px 14px;background:#1A1410;color:#F5EDD6;text-align:left;">Característica</th>{headers}</tr></thead>
  <tbody>{rows}</tbody>
</table>"""


def _phases_table() -> str:
    rows = ""
    for i, (phase, duration, desc) in enumerate(PROJECT_PHASES):
        bg = "#F5EDD6" if i % 2 == 0 else "#E8DBC0"
        rows += f"""<tr>
  <td style="padding:10px 14px;background:{bg};font-weight:600;color:#1A1410;white-space:nowrap;">{phase}</td>
  <td style="padding:10px 14px;background:{bg};color:#8A5225;font-weight:600;white-space:nowrap;">{duration}</td>
  <td style="padding:10px 14px;background:{bg};color:#3E2E1E;font-size:13px;">{desc}</td>
</tr>"""
    return f"""
<table style="width:100%;border-collapse:collapse;margin-top:12px;">
  <thead><tr>
    <th style="padding:10px 14px;background:#1A1410;color:#F5EDD6;text-align:left;">Fase</th>
    <th style="padding:10px 14px;background:#1A1410;color:#F5EDD6;text-align:left;">Duración</th>
    <th style="padding:10px 14px;background:#1A1410;color:#F5EDD6;text-align:left;">Descripción</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""


def _pricing_table(tier: str) -> str:
    rows = ""
    for t, p in TIER_PRICING.items():
        highlight = t == tier
        bg = "#C17A3A" if highlight else ("#F5EDD6" if list(TIER_PRICING).index(t) % 2 == 0 else "#E8DBC0")
        color = "#F5EDD6" if highlight else "#1A1410"
        rows += f"""<tr>
  <td style="padding:10px 14px;background:{bg};color:{color};font-weight:{'700' if highlight else '400'};">{p['label']}</td>
  <td style="padding:10px 14px;background:{bg};color:{color};text-align:right;font-weight:{'700' if highlight else '400'};">{p['one_time']:,} €</td>
  <td style="padding:10px 14px;background:{bg};color:{color};text-align:right;font-weight:{'700' if highlight else '400'};">{p['monthly']} €/mes</td>
</tr>"""
    return f"""
<table style="width:100%;border-collapse:collapse;margin-top:12px;">
  <thead><tr>
    <th style="padding:10px 14px;background:#1A1410;color:#F5EDD6;text-align:left;">Plan</th>
    <th style="padding:10px 14px;background:#1A1410;color:#F5EDD6;text-align:right;">Inversión inicial</th>
    <th style="padding:10px 14px;background:#1A1410;color:#F5EDD6;text-align:right;">Cuota mensual</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""


def _case_studies_html() -> str:
    websites_dir = Path("output/websites")
    if not websites_dir.exists():
        return "<p style='color:#888;font-style:italic;'>Casos de éxito disponibles próximamente.</p>"

    html_files = sorted(
        [f for f in websites_dir.rglob("index.html")],
        key=lambda p: p.stat().st_mtime, reverse=True
    )[:3]

    if not html_files:
        return "<p style='color:#888;font-style:italic;'>Casos de éxito disponibles próximamente.</p>"

    cards = ""
    for html_file in html_files:
        parent = html_file.parent.name if html_file.parent != websites_dir else "urdimbre"
        label = parent.replace("-", " ").title()
        cards += f"""
<div style="flex:1;min-width:200px;background:#F5EDD6;border-radius:8px;overflow:hidden;border:1px solid #E8DBC0;">
  <div style="height:120px;background:linear-gradient(135deg,#1A1410 0%,#3E2E1E 100%);display:flex;align-items:center;justify-content:center;">
    <span style="color:#C17A3A;font-family:'Playfair Display',serif;font-size:18px;font-weight:700;">{label[0]}</span>
  </div>
  <div style="padding:12px;">
    <p style="margin:0;font-weight:600;color:#1A1410;font-size:13px;">{label}</p>
    <p style="margin:4px 0 0;color:#8A5225;font-size:11px;">Sitio web corporativo</p>
  </div>
</div>"""

    return f'<div style="display:flex;gap:16px;flex-wrap:wrap;">{cards}</div>'


def build_html(business_name: str, website_status: str, tier: str, date_str: str) -> str:
    analysis = SITE_STATUS_ANALYSIS.get(website_status, SITE_STATUS_ANALYSIS["modern"])
    pricing = TIER_PRICING[tier]

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Plus+Jakarta+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>
  @page {{ size: A4; margin: 20mm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Plus Jakarta Sans', sans-serif; color: #1A1410; background: #fff; }}
  h1 {{ font-family: 'Playfair Display', serif; }}
  h2 {{ font-family: 'Playfair Display', serif; color: #1A1410; font-size: 18px; margin-bottom: 10px; border-bottom: 2px solid #C17A3A; padding-bottom: 6px; }}
  .section {{ margin-bottom: 28px; }}
  p {{ line-height: 1.7; font-size: 13px; color: #3E2E1E; }}
</style>
</head>
<body>

<!-- Cover -->
<div style="background:#1A1410;color:#F5EDD6;padding:40px;margin:-20mm -20mm 0;page-break-after:always;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <p style="font-family:'Plus Jakarta Sans',sans-serif;font-size:11px;letter-spacing:.15em;color:#C17A3A;text-transform:uppercase;margin-bottom:8px;">PROPUESTA COMERCIAL</p>
      <h1 style="font-size:36px;color:#F5EDD6;line-height:1.2;max-width:400px;">{business_name}</h1>
      <p style="margin-top:16px;color:#D9944E;font-size:14px;">{date_str}</p>
    </div>
    <div style="text-align:right;">
      <p style="font-family:'Playfair Display',serif;font-size:22px;color:#C17A3A;font-weight:700;">URDIMBRE</p>
      <p style="font-size:11px;color:#8A5225;letter-spacing:.08em;text-transform:uppercase;">Diseño Web Profesional</p>
    </div>
  </div>
  <div style="margin-top:60px;padding-top:24px;border-top:1px solid #3E2E1E;">
    <p style="font-size:12px;color:#8A5225;">Preparado por Cifra · adrianarconroyo@gmail.com · Documento confidencial</p>
  </div>
</div>

<!-- Situation -->
<div class="section">
  <h2>1. Situación actual</h2>
  <p>{analysis}</p>
</div>

<!-- Recommended tier -->
<div class="section">
  <h2>2. Plan recomendado: {pricing['label']}</h2>
  <p>Basándonos en las necesidades actuales del negocio, el plan <strong>{pricing['label']}</strong> es el punto de partida ideal.
  Comparativa completa de planes:</p>
  {_tier_features_table(tier)}
</div>

<!-- Phases -->
<div class="section">
  <h2>3. Fases del proyecto</h2>
  {_phases_table()}
</div>

<!-- Pricing -->
<div class="section">
  <h2>4. Inversión</h2>
  <p>El plan <strong>{pricing['label']}</strong> incluye todo lo necesario para lanzar y mantener su presencia web.</p>
  {_pricing_table(tier)}
  <p style="margin-top:10px;font-size:11px;color:#8A5225;">* IVA no incluido. Precios en EUR. La cuota mensual cubre hosting, SSL, backups y soporte.</p>
</div>

<!-- Case studies -->
<div class="section">
  <h2>5. Casos de éxito</h2>
  <p style="margin-bottom:12px;">Ejemplos recientes de sitios web desarrollados por Cifra:</p>
  {_case_studies_html()}
</div>

<!-- Next steps -->
<div class="section">
  <h2>6. Próximos pasos</h2>
  <p>Para comenzar, basta con confirmar el plan elegido y firmar el contrato de servicios.
  El proyecto arranca en 48 horas desde la firma.</p>
  <div style="margin-top:16px;background:#F5EDD6;border-left:4px solid #C17A3A;padding:16px;">
    <p><strong>¿Listo para dar el siguiente paso?</strong><br>
    Responda a este email o escríbanos a adrianarconroyo@gmail.com para coordinar una llamada.</p>
  </div>
</div>

<!-- Signature -->
<div style="margin-top:40px;display:flex;gap:60px;">
  <div>
    <div style="width:200px;border-top:1px solid #1A1410;padding-top:8px;">
      <p style="font-size:11px;color:#8A5225;">Firma del Cliente</p>
      <p style="font-size:11px;color:#8A5225;margin-top:4px;">{business_name}</p>
    </div>
  </div>
  <div>
    <div style="width:200px;border-top:1px solid #1A1410;padding-top:8px;">
      <p style="font-size:11px;color:#8A5225;">Adrián Arcon Royo</p>
      <p style="font-size:11px;color:#8A5225;margin-top:4px;">Cifra</p>
    </div>
  </div>
</div>

<div style="margin-top:30px;padding-top:12px;border-top:1px solid #E8DBC0;">
  <p style="font-size:10px;color:#aaa;text-align:center;">Documento confidencial — Cifra © {datetime.now().year}. No distribuir sin autorización escrita.</p>
</div>

</body>
</html>"""


def generate_pdf(business_name: str, website_status: str, tier: str) -> Path:
    date_str = datetime.now().strftime("%d/%m/%Y")
    date_file = datetime.now().strftime("%Y-%m-%d")
    slug = _slug(business_name)

    out_dir = Path(f"output/proposals/{slug}")
    out_dir.mkdir(parents=True, exist_ok=True)

    html_content = build_html(business_name, website_status, tier, date_str)

    html_path = out_dir / f"proposal_{date_file}.html"
    html_path.write_text(html_content, encoding="utf-8")

    pdf_path = out_dir / f"proposal_{date_file}.pdf"

    import sys as _sys
    _root = str(Path(__file__).parent.parent)
    if _root not in _sys.path:
        _sys.path.insert(0, _root)
    from tools.pdf_engine import render_pdf
    pdf_path = render_pdf(html_content, pdf_path)
    print(f"[OK] PDF → {pdf_path}")

    return pdf_path


def run(lead_id: int | None, brief: str | None, tier: str) -> Path:
    if lead_id is not None:
        from tools.db import get_lead
        lead = get_lead(lead_id)
        if not lead:
            print(f"[ERROR] Lead {lead_id} not found.")
            sys.exit(1)
        business_name = lead["business_name"]
        website_status = lead.get("website_status", "modern")
    elif brief:
        business_name = brief.strip()
        website_status = "no_site"
    else:
        print("[ERROR] Provide --lead-id or --brief")
        sys.exit(1)

    print(f"\n[Proposal] {business_name} | Tier: {tier}")
    pdf_path = generate_pdf(business_name, website_status, tier)
    print(f"[DONE] {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate commercial proposal PDF")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lead-id", type=int)
    group.add_argument("--brief", type=str, help='e.g. "Restaurante en Madrid, sin web"')
    parser.add_argument("--tier", default="basic", choices=list(TIER_PRICING.keys()))
    args = parser.parse_args()
    run(args.lead_id, args.brief, args.tier)
