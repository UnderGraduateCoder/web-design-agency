"""
generate_quote_pdf.py

Usage:
    python tools/generate_quote_pdf.py <path/to/quote.json>
    python tools/generate_quote_pdf.py output/quotes/acme/quote_1_2026-04-16.json

Generates a professional PDF quote in Spanish using WeasyPrint.
Output: same directory as the input JSON, with .pdf extension.

Requires:
    pip install weasyprint
    On Windows: GTK runtime — https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer

Typography: Playfair Display (headings) + Plus Jakarta Sans (body)
Color palette: Copper #C17A3A / Linen #F5EDD6 / Charcoal #1A1410
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Colour & typography constants (matches generate_audit_pdf.py)
# ---------------------------------------------------------------------------

COPPER    = "#C17A3A"
COPPER_DK = "#8A5225"
COPPER_LT = "#D9944E"
LINEN     = "#F5EDD6"
LINEN_DK  = "#E8DBC0"
CHARCOAL  = "#1A1410"
TEXT_BODY = "#4A3825"
WHITE     = "#FFFFFF"

# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _tag(text: str, bg: str, fg: str = WHITE) -> str:
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px;'
        f'letter-spacing:0.04em;">{text}</span>'
    )


def _line_item_rows(line_items: list) -> str:
    rows = []
    for i, li in enumerate(line_items):
        bg = "#fafaf8" if i % 2 == 0 else WHITE
        included = li.get("included_in_tier", False)
        tag_html = _tag("Incluido", COPPER_DK) if included else ""
        subtotal_display = (
            f'<span style="color:{COPPER_DK};text-decoration:line-through;font-size:10px;">'
            f'€{li["unit_price"] * li.get("quantity", 1):.2f}</span> €0.00'
            if included
            else f'€{li.get("subtotal", 0):.2f}'
        )
        rows.append(f"""
        <tr style="background:{bg};">
            <td style="padding:10px 8px;font-size:10px;color:{CHARCOAL};width:80px;">{li.get("code","")}</td>
            <td style="padding:10px 8px;font-size:11px;color:{CHARCOAL};">
                {li.get("description_es","—")} {tag_html}
            </td>
            <td style="padding:10px 8px;text-align:center;font-size:11px;">{li.get("quantity",1)}</td>
            <td style="padding:10px 8px;text-align:right;font-size:11px;">€{li.get("unit_price",0):.2f}</td>
            <td style="padding:10px 8px;text-align:right;font-size:11px;font-weight:600;">{subtotal_display}</td>
        </tr>
        """)
    return "".join(rows)


def build_html(quote: dict) -> str:
    client_name   = quote.get("client_name", quote.get("client_slug", "—"))
    tier          = quote.get("tier", "—").upper()
    quote_date    = quote.get("quote_date", datetime.now().strftime("%Y-%m-%d"))
    quote_number  = quote.get("quote_number", 1)
    line_items    = quote.get("line_items", [])
    gross         = quote.get("subtotal_gross", 0)
    credits       = quote.get("tier_credits_applied", 0)
    net           = quote.get("subtotal_net", 0)
    vat           = quote.get("vat_21", 0)
    total         = quote.get("total", 0)
    terms         = quote.get("payment_terms_es", "50% al aprobar, 50% a la entrega")
    delivery_days = quote.get("estimated_delivery_days", 7)

    google_fonts = (
        "https://fonts.googleapis.com/css2?"
        "family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&"
        "family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"
    )

    item_count = len(line_items)
    included_count = sum(1 for li in line_items if li.get("included_in_tier"))

    rows_html = _line_item_rows(line_items)

    credits_row = ""
    if credits > 0:
        credits_row = f"""
        <tr style="color:{COPPER_DK};">
            <td colspan="4" style="padding:8px;text-align:right;font-size:11px;">
                Créditos incluidos en tier {quote.get("tier","").upper()} ({included_count} cambio/s)
            </td>
            <td style="padding:8px;text-align:right;font-size:11px;font-weight:600;">
                −€{credits:.2f}
            </td>
        </tr>
        """

    custom_warning = ""
    has_custom = any(li.get("code") == "custom" for li in line_items)
    if has_custom:
        custom_warning = f"""
        <div style="margin:16px 0;padding:12px 16px;background:#FFF8E1;border-left:4px solid #F59E0B;
                    font-size:11px;color:#7c5c00;font-family:'Plus Jakarta Sans',sans-serif;">
            <strong>⚠ Atención:</strong> Este presupuesto contiene ítem(s) de tipo <em>Personalizado</em>
            que requieren precio manual. Revisa y actualiza el JSON antes de enviar al cliente.
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Presupuesto #{quote_number} — {client_name}</title>
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
  table {{ border-collapse: collapse; width: 100%; }}
</style>
</head>
<body>

<!-- COVER STRIP -->
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
      <div>Presupuesto nº: <strong style="color:{WHITE};">{str(quote_number).zfill(4) if str(quote_number).isdigit() else quote_number}</strong></div>
      <div style="margin-top:4px;">Fecha: {quote_date}</div>
      <div style="margin-top:4px;">Tier cliente: {tier}</div>
    </div>
  </div>
  <div style="margin-top:36px;">
    <h1 style="font-size:32px;font-weight:700;color:{WHITE};line-height:1.2;">
      Presupuesto de<br>Cambios Web
    </h1>
    <div style="margin-top:12px;font-size:16px;color:{COPPER_LT};font-family:'Playfair Display',serif;
                font-style:italic;">
      {client_name}
    </div>
  </div>
</div>

<!-- SUMMARY STRIP -->
<div style="display:flex;background:{LINEN};border-bottom:2px solid {LINEN_DK};padding:16px 40px;gap:40px;">
  <div style="text-align:center;">
    <div style="font-size:28px;font-weight:700;color:{CHARCOAL};font-family:'Playfair Display',serif;">
      {item_count}
    </div>
    <div style="font-size:10px;letter-spacing:0.08em;color:{TEXT_BODY};">ÍTEMS</div>
  </div>
  <div style="text-align:center;">
    <div style="font-size:28px;font-weight:700;color:{TEXT_BODY};font-family:'Playfair Display',serif;">
      €{gross:.0f}
    </div>
    <div style="font-size:10px;letter-spacing:0.08em;color:{TEXT_BODY};">BRUTO</div>
  </div>
  <div style="text-align:center;">
    <div style="font-size:28px;font-weight:700;color:{COPPER_DK};font-family:'Playfair Display',serif;">
      −€{credits:.0f}
    </div>
    <div style="font-size:10px;letter-spacing:0.08em;color:{TEXT_BODY};">CRÉDITOS TIER</div>
  </div>
  <div style="text-align:center;">
    <div style="font-size:28px;font-weight:700;color:{COPPER};font-family:'Playfair Display',serif;">
      €{total:.2f}
    </div>
    <div style="font-size:10px;letter-spacing:0.08em;color:{TEXT_BODY};">TOTAL IVA incl.</div>
  </div>
</div>

<!-- MAIN CONTENT -->
<div style="padding:32px 40px;">

  {custom_warning}

  <!-- CONTEXT NOTE -->
  <p style="margin-bottom:24px;font-size:11px;color:{TEXT_BODY};line-height:1.7;">
    El presente presupuesto recoge los trabajos solicitados por <strong>{client_name}</strong>
    con fecha <strong>{quote_date}</strong>. Los ítems marcados como <em>Incluido</em> forman
    parte de los cambios mensuales gratuitos correspondientes al tier <strong>{tier}</strong>.
    El resto se factura según las condiciones indicadas al pie.
  </p>

  <!-- LINE ITEMS TABLE -->
  <h2 style="font-size:20px;color:{COPPER};border-bottom:1px solid {LINEN_DK};
             padding-bottom:8px;margin-bottom:16px;">
    Detalle de Trabajos
  </h2>

  <table style="border:1px solid {LINEN_DK};font-family:'Plus Jakarta Sans',sans-serif;font-size:11px;">
    <thead>
      <tr style="background:{LINEN_DK};">
        <th style="padding:8px;text-align:left;font-size:10px;color:{CHARCOAL};width:90px;">Código</th>
        <th style="padding:8px;text-align:left;font-size:10px;color:{CHARCOAL};">Descripción</th>
        <th style="padding:8px;text-align:center;font-size:10px;color:{CHARCOAL};width:50px;">Cant.</th>
        <th style="padding:8px;text-align:right;font-size:10px;color:{CHARCOAL};width:90px;">Precio unit.</th>
        <th style="padding:8px;text-align:right;font-size:10px;color:{CHARCOAL};width:90px;">Subtotal</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>

  <!-- TOTALS BLOCK -->
  <table style="margin-top:0;border:1px solid {LINEN_DK};border-top:none;
                font-family:'Plus Jakarta Sans',sans-serif;font-size:11px;">
    <tbody>
      <tr style="background:{WHITE};">
        <td colspan="4" style="padding:8px 8px;text-align:right;color:{TEXT_BODY};">
          Subtotal bruto
        </td>
        <td style="padding:8px;text-align:right;width:90px;">€{gross:.2f}</td>
      </tr>
      {credits_row}
      <tr style="background:{WHITE};">
        <td colspan="4" style="padding:8px;text-align:right;color:{TEXT_BODY};">
          Subtotal neto
        </td>
        <td style="padding:8px;text-align:right;font-weight:600;width:90px;">€{net:.2f}</td>
      </tr>
      <tr style="background:{WHITE};">
        <td colspan="4" style="padding:8px;text-align:right;color:{TEXT_BODY};">
          IVA (21%)
        </td>
        <td style="padding:8px;text-align:right;width:90px;">€{vat:.2f}</td>
      </tr>
      <tr style="background:{LINEN};font-weight:700;border-top:2px solid {COPPER};">
        <td colspan="4" style="padding:12px 8px;text-align:right;font-size:13px;">
          TOTAL
        </td>
        <td style="padding:12px 8px;text-align:right;color:{COPPER};font-size:16px;width:90px;">
          €{total:.2f}
        </td>
      </tr>
    </tbody>
  </table>

  <!-- PAYMENT TERMS & DELIVERY -->
  <div style="margin-top:28px;display:flex;gap:24px;">
    <div style="flex:1;padding:16px;background:{LINEN};border-left:4px solid {COPPER};">
      <h3 style="font-family:'Playfair Display',serif;font-size:13px;color:{COPPER};margin-bottom:8px;">
        Condiciones de Pago
      </h3>
      <p style="font-size:11px;color:{TEXT_BODY};">{terms}</p>
    </div>
    <div style="flex:1;padding:16px;background:{LINEN};border-left:4px solid {COPPER_DK};">
      <h3 style="font-family:'Playfair Display',serif;font-size:13px;color:{COPPER_DK};margin-bottom:8px;">
        Plazo de Entrega
      </h3>
      <p style="font-size:11px;color:{TEXT_BODY};">
        Estimado: <strong>{delivery_days} días hábiles</strong> desde la aprobación y recepción del 50% inicial.
      </p>
    </div>
  </div>

  <!-- SIGNATURE BLOCK -->
  <div style="margin-top:48px;display:flex;gap:60px;">
    <div style="flex:1;">
      <div style="border-top:1px solid {CHARCOAL};padding-top:8px;font-size:11px;color:{TEXT_BODY};">
        <strong>Aprobado por {client_name}</strong><br>
        Nombre y cargo: ___________________<br>
        Fecha: ___________________
      </div>
    </div>
    <div style="flex:1;">
      <div style="border-top:1px solid {CHARCOAL};padding-top:8px;font-size:11px;color:{TEXT_BODY};">
        <strong>Por Cifra</strong><br>
        Responsable del proyecto<br>
        Fecha: ___________________
      </div>
    </div>
  </div>

  <!-- CONFIDENTIALITY NOTICE -->
  <div style="margin-top:32px;font-size:9px;color:#aaa;text-align:center;
              border-top:1px solid {LINEN_DK};padding-top:12px;">
    Este presupuesto es CONFIDENCIAL y tiene validez de 30 días desde su emisión.
    Pasado ese plazo, los precios podrían estar sujetos a revisión. Su distribución está
    restringida a las partes firmantes. Cifra — CIF: [PENDIENTE] — hola@cifra.studio
  </div>

</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# PDF / HTML writer
# ---------------------------------------------------------------------------

def generate_pdf(quote_json_path: str | Path) -> Path:
    quote_path = Path(quote_json_path)
    with open(quote_path, encoding="utf-8") as f:
        quote = json.load(f)

    html_content = build_html(quote)
    out_pdf = quote_path.with_suffix(".pdf")
    out_html = quote_path.with_suffix(".html")

    import sys as _sys
    _root = str(Path(__file__).parent.parent)
    if _root not in _sys.path:
        _sys.path.insert(0, _root)
    from tools.pdf_engine import render_pdf
    result = render_pdf(html_content, out_pdf)
    print(f"PDF guardado en: {result}")
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Genera un PDF de presupuesto a partir de un quote.json."
    )
    parser.add_argument("quote_json", help="Ruta al archivo quote JSON")
    args = parser.parse_args()

    path = Path(args.quote_json)
    if not path.exists():
        print(f"Error: no se encontró el archivo {path}", file=sys.stderr)
        sys.exit(1)

    generate_pdf(path)


if __name__ == "__main__":
    main()
