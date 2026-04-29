"""
generate_audit_pdf.py

Usage:
    python tools/generate_audit_pdf.py <findings.json> <client_slug>
    python tools/generate_audit_pdf.py output/audits/acme-corp/findings.json acme-corp

Generates a professional PDF audit report in Spanish using WeasyPrint.
Output: output/audits/{client_slug}/report_{YYYY-MM-DD}.pdf

Requires:
    pip install weasyprint
    On Windows: GTK runtime — https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer

Typography: Playfair Display (headings) + Plus Jakarta Sans (body)
Color palette: Copper #C17A3A / Linen #F5EDD6 / Charcoal #1A1410
"""

import sys
import json
import argparse
from datetime import date, datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Colour & typography constants
# ---------------------------------------------------------------------------

COPPER    = "#C17A3A"
COPPER_DK = "#8A5225"
COPPER_LT = "#D9944E"
LINEN     = "#F5EDD6"
LINEN_DK  = "#E8DBC0"
CHARCOAL  = "#1A1410"
TEXT_BODY = "#4A3825"
WHITE     = "#FFFFFF"

SEV_COLORS = {
    "HIGH":   ("#C0392B", WHITE, "Alta"),
    "MEDIUM": ("#E67E22", WHITE, "Media"),
    "LOW":    ("#27AE60", WHITE, "Baja"),
}

# ---------------------------------------------------------------------------
# Pricing import
# ---------------------------------------------------------------------------

try:
    from calculate_audit_price import calculate as _calc_price
except ImportError:
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    from calculate_audit_price import calculate as _calc_price

# ---------------------------------------------------------------------------
# DB import (optional — used for client branding)
# ---------------------------------------------------------------------------

try:
    from db import get_client
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False


# ---------------------------------------------------------------------------
# HTML template helpers
# ---------------------------------------------------------------------------

def _badge(text: str, bg: str, fg: str = WHITE) -> str:
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'font-size:9px;font-weight:700;padding:2px 7px;border-radius:4px;'
        f'letter-spacing:0.04em;margin:1px;">{text}</span>'
    )


def _compliance_badges(compliance: dict) -> str:
    parts = []
    for ref in compliance.get("owasp", []):
        parts.append(_badge(ref, "#C0392B"))
    for ref in compliance.get("iso27001", []):
        parts.append(_badge(ref, "#003087"))
    for ref in compliance.get("rgpd", []):
        parts.append(_badge(ref, "#003399"))
    return " ".join(parts) if parts else '<span style="color:#999;font-size:9px;">—</span>'


def _severity_badge(severity: str) -> str:
    bg, fg, label = SEV_COLORS.get(severity.upper(), ("#888", WHITE, severity))
    return _badge(label, bg, fg)


def _finding_row(f: dict, index: int) -> str:
    sev = f.get("severity", "LOW")
    compliance = f.get("compliance", {})
    file_info = f.get("file_path", "—")
    line_info = f.get("line_number")
    location = f"{file_info}:{line_info}" if line_info else file_info

    return f"""
    <tr style="background:{'#fafaf8' if index % 2 == 0 else WHITE};">
        <td style="padding:10px 8px;vertical-align:top;width:70px;text-align:center;">
            {_severity_badge(sev)}
        </td>
        <td style="padding:10px 8px;vertical-align:top;font-size:11px;color:{CHARCOAL};">
            <strong>{f.get('description', '—')}</strong><br>
            <span style="color:#888;font-size:10px;">{location}</span>
        </td>
        <td style="padding:10px 8px;vertical-align:top;font-size:10px;color:{TEXT_BODY};">
            {f.get('recommendation', '—')}
        </td>
        <td style="padding:10px 8px;vertical-align:top;">
            {_compliance_badges(compliance)}
        </td>
    </tr>
    """


def _findings_section(findings: list[dict], severity: str, label_es: str) -> str:
    items = [f for f in findings if f.get("severity", "").upper() == severity]
    if not items:
        return ""
    bg, _, _ = SEV_COLORS[severity]
    rows = "".join(_finding_row(f, i) for i, f in enumerate(items))
    return f"""
    <h3 style="font-family:'Playfair Display',serif;color:{bg};
               margin:28px 0 8px;font-size:15px;border-left:4px solid {bg};
               padding-left:10px;">
        Hallazgos — Severidad {label_es} ({len(items)})
    </h3>
    <table style="width:100%;border-collapse:collapse;font-family:'Plus Jakarta Sans',sans-serif;
                  border:1px solid {LINEN_DK};font-size:11px;">
        <thead>
            <tr style="background:{LINEN_DK};">
                <th style="padding:8px;text-align:center;font-size:10px;color:{CHARCOAL};">Severidad</th>
                <th style="padding:8px;text-align:left;font-size:10px;color:{CHARCOAL};">Descripción / Ubicación</th>
                <th style="padding:8px;text-align:left;font-size:10px;color:{CHARCOAL};">Recomendación</th>
                <th style="padding:8px;text-align:left;font-size:10px;color:{CHARCOAL};">Normativas</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
    """


def _price_section(quote: dict) -> str:
    items_html = ""
    for li in quote.get("line_items", []):
        items_html += f"""
        <tr>
            <td style="padding:7px 8px;">{li['description']}</td>
            <td style="padding:7px 8px;text-align:center;">{li['quantity']}</td>
            <td style="padding:7px 8px;text-align:right;">€{li['unit_price']:.0f}</td>
            <td style="padding:7px 8px;text-align:right;font-weight:600;">€{li['subtotal']:.0f}</td>
        </tr>
        """

    discount_row = ""
    if quote.get("discount_pct", 0):
        discount_row = f"""
        <tr style="color:{COPPER_DK};">
            <td colspan="3" style="padding:7px 8px;text-align:right;">
                Descuento por volumen ({quote['discount_pct']}%)
            </td>
            <td style="padding:7px 8px;text-align:right;font-weight:600;">
                −€{quote['discount_amount']:.0f}
            </td>
        </tr>
        """

    return f"""
    <h3 style="font-family:'Playfair Display',serif;color:{COPPER};
               margin:28px 0 8px;font-size:15px;border-left:4px solid {COPPER};
               padding-left:10px;">
        Plan de Remediación — Presupuesto
    </h3>
    <table style="width:100%;border-collapse:collapse;font-family:'Plus Jakarta Sans',sans-serif;
                  border:1px solid {LINEN_DK};font-size:11px;">
        <thead>
            <tr style="background:{LINEN_DK};">
                <th style="padding:8px;text-align:left;">Concepto</th>
                <th style="padding:8px;text-align:center;">Cant.</th>
                <th style="padding:8px;text-align:right;">Precio unit.</th>
                <th style="padding:8px;text-align:right;">Subtotal</th>
            </tr>
        </thead>
        <tbody>
            {items_html}
            {discount_row}
            <tr style="background:{LINEN};font-weight:700;border-top:2px solid {COPPER};">
                <td colspan="3" style="padding:10px 8px;text-align:right;">
                    Total remediación (IVA no incluido)
                </td>
                <td style="padding:10px 8px;text-align:right;color:{COPPER};font-size:14px;">
                    €{quote['remediation_total']:.0f}
                </td>
            </tr>
        </tbody>
    </table>
    <p style="margin:12px 0 0;font-size:11px;color:{TEXT_BODY};">
        <strong>Monitorización mensual continua:</strong>
        €{quote['monthly_monitoring']:.0f}/mes — incluye auditoría recurrente, informe comparativo
        y seguimiento de hallazgos resueltos.
    </p>
    """


# ---------------------------------------------------------------------------
# Full HTML report
# ---------------------------------------------------------------------------

def build_html(findings_data: dict, client_info: dict | None, quote: dict) -> str:
    slug       = findings_data.get("client_slug", "—")
    target     = findings_data.get("target", "—")
    scan_mode  = findings_data.get("scan_mode", "repo")
    scan_date  = findings_data.get("scan_date", datetime.now().isoformat())[:10]
    summary    = findings_data.get("summary", {})
    findings   = findings_data.get("findings", [])

    biz_name   = (client_info or {}).get("business_name", slug)
    tier       = (client_info or {}).get("tier", "—")

    scan_mode_labels = {
        "repo": "Análisis de Repositorio",
        "public_url": "Análisis de URL Pública",
        "pre_launch": "Análisis Pre-lanzamiento",
        "website_build": "Análisis del Bundle Web",
    }
    scan_label = scan_mode_labels.get(scan_mode, scan_mode)

    findings_html = (
        _findings_section(findings, "HIGH", "Alta") +
        _findings_section(findings, "MEDIUM", "Media") +
        _findings_section(findings, "LOW", "Baja")
    ) or "<p style='color:#888;'>No se detectaron hallazgos.</p>"

    price_html = _price_section(quote) if findings else ""

    google_fonts = (
        "https://fonts.googleapis.com/css2?"
        "family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&"
        "family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"
    )

    compliance_legend = f"""
    <div style="margin:24px 0 8px;font-family:'Plus Jakarta Sans',sans-serif;font-size:10px;color:{TEXT_BODY};">
        <strong>Leyenda de normativas:</strong>&nbsp;&nbsp;
        {_badge('OWASP Top 10', '#C0392B')}&nbsp;Categoría OWASP 2021 &nbsp;|&nbsp;
        {_badge('ISO 27001', '#003087')}&nbsp;Control Anexo A &nbsp;|&nbsp;
        {_badge('RGPD', '#003399')}&nbsp;Artículo RGPD (UE) 2016/679
    </div>
    """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Informe de Auditoría de Seguridad — {biz_name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{google_fonts}" rel="stylesheet">
<style>
  @page {{
    size: A4;
    margin: 20mm 18mm 20mm 18mm;
    @bottom-center {{
      content: "Cifra — Confidencial — Página " counter(page) " de " counter(pages);
      font-size: 9px;
      color: #888;
      font-family: 'Plus Jakarta Sans', sans-serif;
    }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: {CHARCOAL};
    background: {WHITE};
    font-size: 12px;
    line-height: 1.6;
  }}
  h1, h2, h3, h4 {{ font-family: 'Playfair Display', serif; }}
</style>
</head>
<body>

<!-- COVER PAGE -->
<div style="background:{CHARCOAL};color:{LINEN};padding:48px 40px;min-height:180px;
            border-bottom:4px solid {COPPER};">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div style="font-family:'Playfair Display',serif;font-size:28px;
                  font-weight:700;letter-spacing:-0.02em;color:{WHITE};">
        Cifra
      </div>
    </div>
    <div style="text-align:right;font-size:10px;color:{LINEN_DK};">
      <div>Fecha: {scan_date}</div>
      <div style="margin-top:4px;">Modo: {scan_label}</div>
      <div style="margin-top:4px;">Tier: {tier.upper()}</div>
    </div>
  </div>
  <div style="margin-top:36px;">
    <h1 style="font-size:32px;font-weight:700;color:{WHITE};line-height:1.2;">
      Informe de Auditoría<br>de Seguridad
    </h1>
    <div style="margin-top:12px;font-size:16px;color:{COPPER_LT};font-family:'Playfair Display',serif;
                font-style:italic;">
      {biz_name}
    </div>
    <div style="margin-top:6px;font-size:10px;color:{LINEN_DK};">Objetivo: {target}</div>
  </div>
</div>

<!-- SUMMARY STRIP -->
<div style="display:flex;background:{LINEN};border-bottom:2px solid {LINEN_DK};padding:16px 40px;gap:40px;">
  <div style="text-align:center;">
    <div style="font-size:28px;font-weight:700;color:#C0392B;font-family:'Playfair Display',serif;">
      {summary.get('high', 0)}
    </div>
    <div style="font-size:10px;letter-spacing:0.08em;color:{TEXT_BODY};">ALTA</div>
  </div>
  <div style="text-align:center;">
    <div style="font-size:28px;font-weight:700;color:#E67E22;font-family:'Playfair Display',serif;">
      {summary.get('medium', 0)}
    </div>
    <div style="font-size:10px;letter-spacing:0.08em;color:{TEXT_BODY};">MEDIA</div>
  </div>
  <div style="text-align:center;">
    <div style="font-size:28px;font-weight:700;color:#27AE60;font-family:'Playfair Display',serif;">
      {summary.get('low', 0)}
    </div>
    <div style="font-size:10px;letter-spacing:0.08em;color:{TEXT_BODY};">BAJA</div>
  </div>
  <div style="text-align:center;">
    <div style="font-size:28px;font-weight:700;color:{CHARCOAL};font-family:'Playfair Display',serif;">
      {summary.get('files_reviewed', 0)}
    </div>
    <div style="font-size:10px;letter-spacing:0.08em;color:{TEXT_BODY};">ARCHIVOS</div>
  </div>
</div>

<!-- MAIN CONTENT -->
<div style="padding:32px 40px;">

  <!-- EXECUTIVE SUMMARY -->
  <h2 style="font-size:20px;color:{COPPER};border-bottom:1px solid {LINEN_DK};
             padding-bottom:8px;margin-bottom:16px;">
    Resumen Ejecutivo
  </h2>
  <p style="margin-bottom:10px;">
    Se ha realizado una auditoría de seguridad de tipo <strong>{scan_label}</strong> sobre el sistema
    <em>{biz_name}</em> ({target}) con fecha <strong>{scan_date}</strong>.
  </p>
  <p style="margin-bottom:10px;">
    El análisis ha identificado un total de <strong>{summary.get('total', 0)} hallazgos</strong>:
    <span style="color:#C0392B;font-weight:600;">{summary.get('high', 0)} de severidad Alta</span>,
    <span style="color:#E67E22;font-weight:600;">{summary.get('medium', 0)} de severidad Media</span> y
    <span style="color:#27AE60;font-weight:600;">{summary.get('low', 0)} de severidad Baja</span>.
  </p>
  <p style="margin-bottom:10px;">
    Los hallazgos de severidad Alta requieren atención inmediata, ya que representan riesgos de
    explotación directa con potencial impacto en la confidencialidad, integridad o disponibilidad
    del sistema. Los hallazgos de severidad Media deben abordarse en el ciclo de desarrollo siguiente.
    Los de severidad Baja corresponden a mejoras de defensa en profundidad.
  </p>
  <p style="margin-bottom:24px;">
    Todos los hallazgos han sido mapeados a los estándares
    <strong>OWASP Top 10 (2021)</strong>,
    <strong>ISO/IEC 27001:2022 Anexo A</strong> y
    <strong>RGPD (UE) 2016/679</strong> para facilitar el cumplimiento normativo.
  </p>

  {compliance_legend}

  <!-- FINDINGS BY SEVERITY -->
  {findings_html}

  <!-- REMEDIATION PLAN & PRICING -->
  {price_html}

  <!-- COMPLIANCE NOTE -->
  <div style="margin-top:32px;padding:16px;background:{LINEN};border-left:4px solid {COPPER};
              font-size:11px;color:{TEXT_BODY};">
    <strong>Nota de cumplimiento RGPD:</strong> De conformidad con el
    <strong>Artículo 32 del RGPD</strong> (Seguridad del Tratamiento), el responsable del
    tratamiento debe implementar medidas técnicas y organizativas apropiadas para garantizar
    un nivel de seguridad adecuado al riesgo. Los hallazgos marcados con el badge RGPD
    afectan directamente a esta obligación legal.
  </div>

  <!-- SIGNATURE BLOCK -->
  <div style="margin-top:48px;display:flex;gap:60px;">
    <div style="flex:1;">
      <div style="border-top:1px solid {CHARCOAL};padding-top:8px;font-size:11px;color:{TEXT_BODY};">
        <strong>Por Cifra</strong><br>
        Responsable de Auditoría de Seguridad<br>
        Fecha: ___________________
      </div>
    </div>
    <div style="flex:1;">
      <div style="border-top:1px solid {CHARCOAL};padding-top:8px;font-size:11px;color:{TEXT_BODY};">
        <strong>Por {biz_name}</strong><br>
        Representante Legal / Responsable Técnico<br>
        Fecha: ___________________
      </div>
    </div>
  </div>

  <!-- CONFIDENTIALITY NOTICE -->
  <div style="margin-top:32px;font-size:9px;color:#aaa;text-align:center;
              border-top:1px solid {LINEN_DK};padding-top:12px;">
    Este informe es CONFIDENCIAL. Contiene información sensible sobre vulnerabilidades de seguridad.
    Su distribución está restringida a las partes firmantes. Está prohibida su reproducción o
    divulgación sin consentimiento escrito de Cifra.
  </div>

</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# fpdf2 fallback renderer (pure Python, no system dependencies)
# ---------------------------------------------------------------------------

def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _build_pdf_fpdf2(
    findings_data: dict,
    client_info: dict | None,
    quote: dict,
    out_pdf: Path,
) -> Path:
    from fpdf import FPDF, XPos, YPos

    slug      = findings_data.get("client_slug", "—")
    target    = findings_data.get("target", "—")
    scan_mode = findings_data.get("scan_mode", "repo")
    scan_date = findings_data.get("scan_date", datetime.now().isoformat())[:10]
    summary   = findings_data.get("summary", {})
    findings  = findings_data.get("findings", [])
    biz_name  = (client_info or {}).get("business_name", slug)
    tier      = (client_info or {}).get("tier", "—")

    scan_labels = {
        "repo": "Análisis de Repositorio",
        "public_url": "Análisis de URL Pública",
        "pre_launch": "Análisis Pre-lanzamiento",
        "website_build": "Análisis del Bundle Web",
    }
    scan_label = scan_labels.get(scan_mode, scan_mode)

    C_COPPER  = _hex(COPPER)
    C_LINEN   = _hex(LINEN)
    C_CHAR    = _hex(CHARCOAL)
    C_BODY    = _hex(TEXT_BODY)
    C_WHITE   = (255, 255, 255)
    C_RED     = (192, 57, 43)
    C_ORANGE  = (230, 126, 34)
    C_GREEN   = (39, 174, 96)
    C_BLUE    = (0, 48, 135)
    C_EUBL    = (0, 51, 153)

    SEV_COLORS_PDF = {
        "HIGH":   (C_RED,    "Alta"),
        "MEDIUM": (C_ORANGE, "Media"),
        "LOW":    (C_GREEN,  "Baja"),
    }

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)

    # Load a Unicode TTF font so Spanish accents render correctly
    _FONT_PATHS = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    _FONT_PATHS_BOLD = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    _FONT_PATHS_ITALIC = [
        "C:/Windows/Fonts/ariali.ttf",
        "C:/Windows/Fonts/calibrii.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    ]
    _font_name = "UniFont"
    _loaded = False
    for reg, bold, italic in zip(_FONT_PATHS, _FONT_PATHS_BOLD, _FONT_PATHS_ITALIC):
        if Path(reg).exists():
            pdf.add_font(_font_name, style="",  fname=reg)
            if Path(bold).exists():
                pdf.add_font(_font_name, style="B", fname=bold)
            else:
                pdf.add_font(_font_name, style="B", fname=reg)
            if Path(italic).exists():
                pdf.add_font(_font_name, style="I", fname=italic)
            else:
                pdf.add_font(_font_name, style="I", fname=reg)
            _loaded = True
            break
    if not _loaded:
        _font_name = "Helvetica"  # last resort — may drop accents

    def _font(style="", size=10):
        pdf.set_font(_font_name, style=style, size=size)

    pdf.add_page()
    pdf.set_margins(18, 18, 18)
    W = pdf.w - 36  # usable width

    def set_color(rgb, fill=False):
        if fill:
            pdf.set_fill_color(*rgb)
        else:
            pdf.set_text_color(*rgb)

    # ---- COVER HEADER ----
    pdf.set_fill_color(*C_CHAR)
    pdf.rect(0, 0, pdf.w, 52, style="F")
    pdf.set_fill_color(*C_COPPER)
    pdf.rect(0, 52, pdf.w, 1.5, style="F")

    pdf.set_xy(18, 12)
    _font("B", 18)
    set_color(C_WHITE)
    pdf.cell(0, 8, "Cifra", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_x(18)
    _font("", 9)
    set_color(C_COPPER)
    pdf.cell(0, 5, f"INFORME DE AUDITORÍA DE SEGURIDAD  |  {scan_label.upper()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_x(18)
    _font("I", 11)
    set_color((209, 153, 78))
    pdf.cell(0, 5, biz_name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(18, 42)
    _font("", 8)
    set_color((200, 200, 180))
    pdf.cell(0, 4, f"Fecha: {scan_date}  |  Tier: {tier.upper()}  |  Objetivo: {target[:70]}")

    # ---- KPI STRIP ----
    pdf.set_y(58)
    _font("B", 9)
    kpis = [
        ("ALTA",    str(summary.get("high", 0)),   C_RED),
        ("MEDIA",   str(summary.get("medium", 0)), C_ORANGE),
        ("BAJA",    str(summary.get("low", 0)),    C_GREEN),
        ("ARCHIVOS", str(summary.get("files_reviewed", 0)), C_CHAR),
    ]
    col_w = W / 4
    for i, (label, val, color) in enumerate(kpis):
        x = 18 + i * col_w
        pdf.set_xy(x, 58)
        _font("B", 22)
        set_color(color)
        pdf.cell(col_w, 10, val, align="C")
        pdf.set_xy(x, 68)
        _font("", 7)
        set_color(C_BODY)
        pdf.cell(col_w, 4, label, align="C")
    pdf.set_y(76)

    # ---- SEPARATOR ----
    pdf.set_fill_color(*_hex(LINEN_DK))
    pdf.rect(18, pdf.get_y(), W, 0.4, style="F")
    pdf.set_y(pdf.get_y() + 4)

    # ---- EXECUTIVE SUMMARY ----
    _font("B", 13)
    set_color(C_COPPER)
    pdf.cell(0, 7, "Resumen Ejecutivo", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_fill_color(*C_COPPER)
    pdf.rect(18, pdf.get_y(), W, 0.5, style="F")
    pdf.set_y(pdf.get_y() + 3)

    total = summary.get("total", 0)
    _font("", 9)
    set_color(C_BODY)
    summary_text = (
        f"Se ha realizado una auditoría de tipo {scan_label} sobre {biz_name} ({target[:50]}) "
        f"con fecha {scan_date}. El análisis ha identificado {total} hallazgo(s): "
        f"{summary.get('high',0)} de severidad Alta, {summary.get('medium',0)} de severidad Media "
        f"y {summary.get('low',0)} de severidad Baja. Los hallazgos han sido mapeados a "
        "OWASP Top 10 (2021), ISO/IEC 27001:2022 Anexo A y RGPD (UE) 2016/679."
    )
    pdf.multi_cell(W, 4.5, summary_text)
    pdf.set_y(pdf.get_y() + 4)

    # ---- FINDINGS TABLE ----
    for sev_key in ("HIGH", "MEDIUM", "LOW"):
        sev_findings = [f for f in findings if f.get("severity", "").upper() == sev_key]
        if not sev_findings:
            continue
        color, label_es = SEV_COLORS_PDF[sev_key]

        _font("B", 11)
        set_color(color)
        pdf.cell(0, 7, f"Hallazgos — Severidad {label_es} ({len(sev_findings)})",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_fill_color(*color)
        pdf.rect(18, pdf.get_y(), W, 0.5, style="F")
        pdf.set_y(pdf.get_y() + 2)

        for idx, f in enumerate(sev_findings):
            if pdf.get_y() > 260:
                pdf.add_page()

            # Row background
            row_bg = _hex(LINEN) if idx % 2 == 0 else (255, 255, 255)
            pdf.set_fill_color(*row_bg)
            row_start_y = pdf.get_y()

            # Severity badge
            pdf.set_fill_color(*color)
            pdf.set_xy(18, row_start_y + 1)
            _font("B", 7)
            set_color(C_WHITE)
            pdf.cell(20, 5, label_es.upper(), align="C", fill=True)

            # Description
            pdf.set_xy(40, row_start_y)
            _font("B", 8)
            set_color(C_CHAR)
            desc = f.get("description", "—")[:80]
            pdf.multi_cell(W - 22, 4, desc)

            loc = f.get("file_path", "")
            if f.get("line_number"):
                loc += f":{f['line_number']}"
            if loc:
                pdf.set_x(40)
                _font("I", 7)
                set_color((150, 150, 150))
                pdf.cell(0, 3.5, loc[:80], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            # Recommendation
            rec = f.get("recommendation", "")
            if rec:
                pdf.set_x(40)
                _font("", 8)
                set_color(C_BODY)
                pdf.multi_cell(W - 22, 4, rec[:120])

            # Compliance badges
            comp = f.get("compliance", {})
            badges = (
                [f"OWASP {r}" for r in comp.get("owasp", [])] +
                [f"ISO {r}" for r in comp.get("iso27001", [])] +
                [f"RGPD {r}" for r in comp.get("rgpd", [])]
            )
            if badges:
                pdf.set_x(40)
                pdf.set_font("Helvetica", "B", 6.5)
                for badge in badges[:6]:
                    bc = C_RED if "OWASP" in badge else C_BLUE if "ISO" in badge else C_EUBL
                    pdf.set_fill_color(*bc)
                    set_color(C_WHITE)
                    pdf.cell(len(badge) * 1.8 + 2, 4, badge, fill=True, align="C")
                    pdf.cell(1, 4, "")
                pdf.ln(5)

            pdf.set_y(pdf.get_y() + 2)
            pdf.set_fill_color(*_hex(LINEN_DK))
            pdf.rect(18, pdf.get_y(), W, 0.3, style="F")
            pdf.set_y(pdf.get_y() + 1)

        pdf.set_y(pdf.get_y() + 4)

    # ---- PRICING SECTION ----
    if findings and quote.get("line_items"):
        if pdf.get_y() > 220:
            pdf.add_page()
        _font("B", 11)
        set_color(C_COPPER)
        pdf.cell(0, 7, "Plan de Remediación — Presupuesto", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_fill_color(*C_COPPER)
        pdf.rect(18, pdf.get_y(), W, 0.5, style="F")
        pdf.set_y(pdf.get_y() + 3)

        # Table header
        pdf.set_fill_color(*C_CHAR)
        _font("B", 8)
        set_color(C_WHITE)
        for header, w in [("Concepto", W - 60), ("Cant.", 15), ("Precio unit.", 25), ("Subtotal", 20)]:
            pdf.cell(w, 5, header, fill=True)
        pdf.ln()

        for li in quote["line_items"]:
            _font("", 8)
            set_color(C_BODY)
            pdf.cell(W - 60, 5, li["description"][:55])
            pdf.cell(15, 5, str(li["quantity"]), align="C")
            pdf.cell(25, 5, f"€{li['unit_price']:.0f}", align="R")
            pdf.cell(20, 5, f"€{li['subtotal']:.0f}", align="R")
            pdf.ln()

        if quote.get("discount_pct"):
            _font("I", 8)
            set_color(C_COPPER)
            pdf.cell(W - 20, 5, f"Descuento por volumen ({quote['discount_pct']}%)", align="R")
            pdf.cell(20, 5, f"-€{quote['discount_amount']:.0f}", align="R")
            pdf.ln()

        pdf.set_fill_color(*C_LINEN)
        _font("B", 10)
        set_color(C_COPPER)
        pdf.cell(W - 20, 7, "TOTAL REMEDIACIÓN (IVA no incluido)", align="R", fill=True)
        pdf.cell(20, 7, f"€{quote['remediation_total']:.0f}", align="R", fill=True)
        pdf.ln(10)

        _font("", 8)
        set_color(C_BODY)
        pdf.multi_cell(W, 4,
            f"Monitorización mensual continua: €{quote['monthly_monitoring']:.0f}/mes — "
            "incluye auditoría recurrente, informe comparativo y seguimiento de hallazgos resueltos.")
        pdf.set_y(pdf.get_y() + 6)

    # ---- SIGNATURE BLOCK ----
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.set_y(pdf.get_y() + 8)
    half = W / 2 - 5
    pdf.set_fill_color(*C_CHAR)
    pdf.rect(18, pdf.get_y(), half, 0.5, style="F")
    pdf.rect(18 + half + 10, pdf.get_y(), half, 0.5, style="F")
    pdf.ln(3)
    _font("B", 8)
    set_color(C_BODY)
    pdf.cell(half, 4, "Por Cifra")
    pdf.cell(10, 4, "")
    pdf.cell(half, 4, f"Por {biz_name[:35]}")
    pdf.ln(4)
    _font("", 7)
    set_color((150, 150, 150))
    pdf.cell(half, 4, "Responsable de Auditoría  |  Fecha: ___________")
    pdf.cell(10, 4, "")
    pdf.cell(half, 4, "Representante Legal  |  Fecha: ___________")
    pdf.ln(12)

    # ---- CONFIDENTIALITY FOOTER ----
    _font("I", 7)
    set_color((180, 180, 180))
    pdf.multi_cell(W, 3.5,
        "CONFIDENCIAL — Este informe contiene información sensible sobre vulnerabilidades. "
        "Distribución restringida a las partes firmantes. Prohibida su reproducción sin "
        "consentimiento escrito de Cifra.", align="C")

    pdf.output(str(out_pdf))
    return out_pdf


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_pdf(findings_json_path: str, client_slug: str) -> Path:
    findings_path = Path(findings_json_path)
    if not findings_path.exists():
        print(f"[ERROR] findings.json not found: {findings_path}", file=sys.stderr)
        sys.exit(1)

    with open(findings_path, encoding="utf-8") as f:
        findings_data = json.load(f)

    # Load client info from DB if available
    client_info = None
    if _DB_AVAILABLE:
        try:
            client_info = get_client(client_slug)
        except Exception:
            pass

    # Calculate pricing
    tier = (client_info or {}).get("tier", "basic")
    quote = _calc_price(findings_data, tier=tier)

    # Build HTML
    html_content = build_html(findings_data, client_info, quote)

    # Output path
    out_dir = PROJECT_ROOT / "output" / "audits" / client_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_pdf = out_dir / f"report_{today}.pdf"

    # Save HTML (always — used by browser fallback and fpdf2 source)
    html_path = out_dir / f"report_{today}.html"
    html_path.write_text(html_content, encoding="utf-8")

    # Try pdf_engine (WeasyPrint → Playwright → html fallback)
    try:
        import sys as _sys
        _root = str(Path(__file__).parent.parent)
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from tools.pdf_engine import render_pdf, active_engine
        result = render_pdf(html_content, out_pdf)
        if result.suffix == ".pdf":
            print(f"[OK] PDF report saved ({active_engine()}): {result}", file=sys.stderr)
            return result
    except Exception:
        pass

    # Fallback: fpdf2 — pure Python, no system dependencies
    try:
        out_pdf = _build_pdf_fpdf2(findings_data, client_info, quote, out_pdf)
        print(f"[OK] PDF report saved (fpdf2): {out_pdf}", file=sys.stderr)
        return out_pdf
    except Exception as e:
        print(f"[WARN] fpdf2 PDF failed ({e}) — HTML report saved: {html_path}", file=sys.stderr)
        return html_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cifra PDF audit report generator")
    parser.add_argument("findings_json", help="Path to findings.json")
    parser.add_argument("client_slug", help="Client slug identifier")
    args = parser.parse_args()

    out = generate_pdf(args.findings_json, args.client_slug)
    print(str(out))
