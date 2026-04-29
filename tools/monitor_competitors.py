"""
Monthly competitive intelligence scanner.

Usage:
    python tools/monitor_competitors.py --client-slug <slug> [--dry-run]

Eligible tiers: pro, premium, enterprise.
Reads competitors registered via db.add_competitor().
Optionally uses PAGESPEED_API_KEY from .env for PageSpeed Insights scores.
Outputs PDF to output/competitor_reports/{slug}/competitive_{YYYY-MM}.pdf
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: ensure project root is on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

import importlib.util as _ilu

def _load_db():
    spec = _ilu.spec_from_file_location("db", PROJECT_ROOT / "tools" / "db.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

db = _load_db()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ELIGIBLE_TIERS = {"pro", "premium", "enterprise"}
PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

URDIMBRE_DIFFERENTIATORS = [
    "Auditorías de seguridad mensuales con informe PDF certificado",
    "Tests A/B automatizados con promoción de variante ganadora",
    "Monitorización de competidores con alertas de cambios de precio",
    "Generación de imágenes con IA a medida para cada cliente",
    "Integración con Google Places para reseñas reales en la web",
    "Blog SEO automatizado con publicación semanal",
    "Soporte vía WhatsApp con respuesta en menos de 2 horas",
    "Panel de rendimiento PageSpeed con histórico mensual",
]

PALETTE = {
    "copper": "#C17A3A",
    "copper_dk": "#8A5225",
    "linen": "#F5EDD6",
    "linen_dk": "#E8DBC0",
    "charcoal": "#1A1410",
    "body": "#4A3825",
    "white": "#FFFFFF",
    "green": "#27AE60",
    "orange": "#E67E22",
    "red": "#C0392B",
}

# ---------------------------------------------------------------------------
# Web scraping helpers
# ---------------------------------------------------------------------------

import ipaddress as _ipaddress
import socket as _socket

_BLOCKED_NETWORKS = [
    _ipaddress.ip_network("127.0.0.0/8"),
    _ipaddress.ip_network("10.0.0.0/8"),
    _ipaddress.ip_network("172.16.0.0/12"),
    _ipaddress.ip_network("192.168.0.0/16"),
    _ipaddress.ip_network("169.254.0.0/16"),
    _ipaddress.ip_network("::1/128"),
    _ipaddress.ip_network("fc00::/7"),
]


def _is_safe_url(url: str) -> bool:
    """Block requests to private/link-local/loopback hosts."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        ip = _ipaddress.ip_address(_socket.gethostbyname(hostname))
        return not any(ip in net for net in _BLOCKED_NETWORKS)
    except Exception:
        return False


def _fetch(url: str, timeout: int = 15) -> tuple[str, int]:
    """Return (html_text, status_code). Never raises."""
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CifraBot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace"), resp.status
    except Exception as exc:
        return "", getattr(exc, "code", 0) or 0


def _parse_meta_keywords(html: str) -> list[str]:
    matches = re.findall(
        r'<meta[^>]+name=["\']keywords["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if not matches:
        matches = re.findall(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']keywords["\']',
            html, re.IGNORECASE,
        )
    raw = matches[0] if matches else ""
    return [k.strip() for k in raw.split(",") if k.strip()]


def _parse_title(html: str) -> str:
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _parse_h1s(html: str) -> list[str]:
    return re.findall(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)


def _detect_pricing(html: str) -> list[str]:
    stripped = re.sub(r"<[^>]+>", " ", html)
    pattern = r"(?:€|EUR|\$|USD|£)\s*\d[\d.,]*|\d[\d.,]*\s*(?:€|EUR|\$|USD|£)"
    return list(set(re.findall(pattern, stripped)))[:20]


def _extract_internal_paths(html: str, base_url: str) -> list[str]:
    from urllib.parse import urlparse, urljoin
    base = urlparse(base_url)
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    paths = set()
    for h in hrefs:
        try:
            parsed = urlparse(urljoin(base_url, h))
            if parsed.netloc == base.netloc and parsed.path not in ("", "/"):
                paths.add(parsed.path.rstrip("/"))
        except Exception:
            pass
    return sorted(paths)


def _find_services_page(html: str, base_url: str) -> str | None:
    candidates = [
        "/servicios", "/services", "/precios", "/pricing",
        "/soluciones", "/solutions", "/productos", "/products",
    ]
    paths = _extract_internal_paths(html, base_url)
    for c in candidates:
        if any(p.startswith(c) or c in p for p in paths):
            from urllib.parse import urljoin
            return urljoin(base_url, c)
    return None


def _pagespeed_scores(url: str, api_key: str) -> dict:
    try:
        import urllib.request
        from urllib.parse import urlencode
        params = urlencode({"url": url, "strategy": "mobile", "key": api_key})
        req_url = f"{PAGESPEED_API}?{params}"
        req = urllib.request.Request(req_url, headers={"User-Agent": "CifraBot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        cats = data.get("lighthouseResult", {}).get("categories", {})
        return {
            "performance": round((cats.get("performance", {}).get("score") or 0) * 100),
            "seo": round((cats.get("seo", {}).get("score") or 0) * 100),
            "accessibility": round((cats.get("accessibility", {}).get("score") or 0) * 100),
        }
    except Exception:
        return {}

# ---------------------------------------------------------------------------
# Per-competitor scan
# ---------------------------------------------------------------------------

def _scan_competitor(competitor: dict, api_key: str | None, dry_run: bool) -> dict:
    url = competitor["competitor_url"]
    print(f"  Scanning {url} …", end=" ", flush=True)

    if not _is_safe_url(url):
        print("[BLOCKED — private/internal host]")
        return {"url": url, "error": "blocked_ssrf", "scan_date": datetime.now().isoformat()}

    if dry_run:
        print("[dry-run]")
        return {
            "url": url,
            "title": "DRY RUN",
            "keywords": [],
            "h1s": [],
            "pricing": [],
            "paths": [],
            "services_content": "",
            "pagespeed": {},
            "scan_date": datetime.now().isoformat(),
            "dry_run": True,
        }

    html, status = _fetch(url)
    if not html:
        print(f"[FAILED status={status}]")
        return {"url": url, "error": f"HTTP {status}", "scan_date": datetime.now().isoformat()}

    scan: dict = {
        "url": url,
        "title": _parse_title(html),
        "keywords": _parse_meta_keywords(html),
        "h1s": _parse_h1s(html),
        "pricing": _detect_pricing(html),
        "paths": _extract_internal_paths(html, url),
        "services_content": "",
        "pagespeed": {},
        "scan_date": datetime.now().isoformat(),
    }

    svc_url = _find_services_page(html, url)
    if svc_url and _is_safe_url(svc_url):
        svc_html, _ = _fetch(svc_url)
        if svc_html:
            scan["services_content"] = re.sub(r"<[^>]+>", " ", svc_html)[:3000]

    if api_key:
        scan["pagespeed"] = _pagespeed_scores(url, api_key)

    print("OK")
    return scan


def _diff_scan(current: dict, previous: dict | None) -> dict:
    if not previous:
        return {"new_pages": [], "removed_pages": [], "new_keywords": [], "pricing_changed": False}
    prev_data = json.loads(previous.get("scan_data_json", "{}"))
    curr_paths = set(current.get("paths", []))
    prev_paths = set(prev_data.get("paths", []))
    curr_kw = set(current.get("keywords", []))
    prev_kw = set(prev_data.get("keywords", []))
    curr_prices = set(current.get("pricing", []))
    prev_prices = set(prev_data.get("pricing", []))
    return {
        "new_pages": sorted(curr_paths - prev_paths),
        "removed_pages": sorted(prev_paths - curr_paths),
        "new_keywords": sorted(curr_kw - prev_kw),
        "pricing_changed": curr_prices != prev_prices,
    }

# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def _score_color(score: int) -> str:
    if score >= 80:
        return PALETTE["green"]
    if score >= 50:
        return PALETTE["orange"]
    return PALETTE["red"]


def _score_badge(score: int | None) -> str:
    if score is None:
        return '<span style="color:#aaa">N/D</span>'
    color = _score_color(score)
    return f'<span style="color:{color};font-weight:700">{score}</span>'


def _build_html(client: dict, scan_results: list[dict], month_label: str) -> str:
    client_name = client.get("business_name") or client.get("slug", "Cliente")
    title = f"Inteligencia Competitiva — {client_name} — {month_label}"

    # --- Executive summary counts ---
    total = len(scan_results)
    with_pricing = sum(1 for r in scan_results if r["scan"].get("pricing"))
    with_new_pages = sum(1 for r in scan_results if r["diff"].get("new_pages"))
    errors = sum(1 for r in scan_results if "error" in r["scan"])

    # --- Performance table rows ---
    perf_rows = ""
    for r in scan_results:
        url = r["scan"]["url"]
        ps = r["scan"].get("pagespeed", {})
        title_text = r["scan"].get("title", "—")[:60]
        perf_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid {PALETTE['linen_dk']};font-size:12px">
            <a href="{url}" style="color:{PALETTE['copper']};text-decoration:none">{url}</a><br>
            <span style="color:{PALETTE['body']};font-size:10px">{title_text}</span>
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid {PALETTE['linen_dk']};text-align:center">{_score_badge(ps.get('performance'))}</td>
          <td style="padding:8px 12px;border-bottom:1px solid {PALETTE['linen_dk']};text-align:center">{_score_badge(ps.get('seo'))}</td>
          <td style="padding:8px 12px;border-bottom:1px solid {PALETTE['linen_dk']};text-align:center">{_score_badge(ps.get('accessibility'))}</td>
        </tr>"""

    # --- Activity section ---
    activity_html = ""
    for r in scan_results:
        url = r["scan"]["url"]
        diff = r["diff"]
        if "error" in r["scan"]:
            activity_html += f'<p style="color:{PALETTE["red"]};font-size:12px">⚠ {url}: {r["scan"]["error"]}</p>'
            continue
        kw_str = ", ".join(r["scan"].get("keywords", [])[:10]) or "—"
        pricing_str = ", ".join(r["scan"].get("pricing", [])[:8]) or "—"
        new_pages_str = (", ".join(diff.get("new_pages", [])[:5]) or "Ninguna") if diff.get("new_pages") else "Ninguna"
        new_kw_str = (", ".join(diff.get("new_keywords", [])[:5]) or "Ninguna") if diff.get("new_keywords") else "Ninguna"
        price_change = "Sí — revisa precios" if diff.get("pricing_changed") else "Sin cambios detectados"
        activity_html += f"""
        <div style="margin-bottom:20px;padding:16px;border-left:4px solid {PALETTE['copper']};background:{PALETTE['linen']};border-radius:0 6px 6px 0">
          <p style="font-weight:700;color:{PALETTE['charcoal']};margin:0 0 8px">{url}</p>
          <table style="width:100%;font-size:11px;color:{PALETTE['body']}">
            <tr><td style="width:35%;padding:3px 0;font-weight:600">Keywords meta</td><td>{kw_str}</td></tr>
            <tr><td style="padding:3px 0;font-weight:600">Precios visibles</td><td>{pricing_str}</td></tr>
            <tr><td style="padding:3px 0;font-weight:600">Páginas nuevas</td><td>{new_pages_str}</td></tr>
            <tr><td style="padding:3px 0;font-weight:600">Keywords nuevas</td><td>{new_kw_str}</td></tr>
            <tr><td style="padding:3px 0;font-weight:600">Cambio de precios</td><td style="color:{'#C0392B' if diff.get('pricing_changed') else PALETTE['body']}">{price_change}</td></tr>
          </table>
        </div>"""

    # --- Upsell hooks ---
    upsell_rows = "".join(
        f'<li style="margin-bottom:8px;font-size:12px;color:{PALETTE["body"]}">{d}</li>'
        for d in URDIMBRE_DIFFERENTIATORS
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
  @page {{
    size: A4;
    margin: 20mm 18mm 20mm 18mm;
    @bottom-center {{
      content: "Cifra Web Agency — Confidencial — Página " counter(page) " de " counter(pages);
      font-size: 9px; color: #888;
    }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Plus Jakarta Sans', sans-serif; color: {PALETTE['body']}; background: white; }}
  h1, h2, h3 {{ font-family: 'Playfair Display', serif; }}
</style>
</head>
<body>

<!-- Cover header -->
<div style="background:{PALETTE['charcoal']};padding:32px 0 20px;margin:-20mm -18mm 0;padding-left:18mm;padding-right:18mm;border-bottom:4px solid {PALETTE['copper']}">
  <p style="font-size:10px;letter-spacing:0.15em;text-transform:uppercase;color:{PALETTE['copper']};margin-bottom:8px">Cifra Web Agency</p>
  <h1 style="font-size:22px;color:{PALETTE['white']};line-height:1.3">{title}</h1>
  <p style="font-size:11px;color:#aaa;margin-top:8px">Generado el {datetime.now().strftime('%d de %B de %Y')}</p>
</div>

<!-- KPI strip -->
<div style="background:{PALETTE['linen']};padding:16px 0;margin:0 -18mm;padding-left:18mm;padding-right:18mm;border-bottom:1px solid {PALETTE['linen_dk']};display:flex;gap:0">
  {"".join(f'<div style="flex:1;text-align:center;border-right:1px solid {PALETTE["linen_dk"]}"><p style="font-family:Playfair Display,serif;font-size:28px;color:{PALETTE["copper"]};font-weight:700">{v}</p><p style="font-size:9px;text-transform:uppercase;letter-spacing:0.1em;color:{PALETTE["body"]}">{l}</p></div>' for v, l in [(total, "Competidores"), (with_pricing, "Con precios"), (with_new_pages, "Con páginas nuevas"), (errors, "Con errores")])}
</div>

<!-- Section: Resumen ejecutivo -->
<div style="margin-top:28px">
  <h2 style="font-size:15px;color:{PALETTE['charcoal']};padding-left:10px;border-left:4px solid {PALETTE['copper']};margin-bottom:12px">Resumen Ejecutivo</h2>
  <p style="font-size:12px;line-height:1.7;color:{PALETTE['body']}">
    Este informe analiza la actividad online de {total} competidor{'es' if total != 1 else ''} de <strong>{client_name}</strong>
    durante el mes de <strong>{month_label}</strong>. Se han detectado {with_new_pages} competidor{'es' if with_new_pages != 1 else ''}
    con páginas nuevas y {with_pricing} con precios visibles en su web.
    {'Se detectaron cambios de precios en al menos un competidor — se recomienda revisión urgente.' if any(r['diff'].get('pricing_changed') for r in scan_results) else 'No se detectaron cambios de precios significativos este mes.'}
  </p>
</div>

<!-- Section: Performance comparison -->
<div style="margin-top:28px">
  <h2 style="font-size:15px;color:{PALETTE['charcoal']};padding-left:10px;border-left:4px solid {PALETTE['copper']};margin-bottom:12px">Comparativa de Rendimiento (PageSpeed)</h2>
  <table style="width:100%;border-collapse:collapse;font-size:12px">
    <thead>
      <tr style="background:{PALETTE['linen_dk']}">
        <th style="padding:10px 12px;text-align:left;font-weight:600">Competidor</th>
        <th style="padding:10px 12px;text-align:center;font-weight:600">Rendimiento</th>
        <th style="padding:10px 12px;text-align:center;font-weight:600">SEO</th>
        <th style="padding:10px 12px;text-align:center;font-weight:600">Accesibilidad</th>
      </tr>
    </thead>
    <tbody>{perf_rows}</tbody>
  </table>
  {'<p style="font-size:10px;color:#aaa;margin-top:6px">* Puntuaciones N/D: PAGESPEED_API_KEY no configurada o error en la consulta.</p>' if not os.getenv('PAGESPEED_API_KEY') else ''}
</div>

<!-- Section: Activity -->
<div style="margin-top:28px">
  <h2 style="font-size:15px;color:{PALETTE['charcoal']};padding-left:10px;border-left:4px solid {PALETTE['copper']};margin-bottom:16px">Actividad Detectada</h2>
  {activity_html}
</div>

<!-- Section: Upsell -->
<div style="margin-top:28px;padding:20px;background:{PALETTE['linen']};border-radius:6px;border:1px solid {PALETTE['linen_dk']}">
  <h2 style="font-size:15px;color:{PALETTE['charcoal']};margin-bottom:12px">Oportunidades — Lo que Cifra ofrece y tus competidores no</h2>
  <ul style="padding-left:18px">{upsell_rows}</ul>
  <p style="margin-top:16px;font-size:11px;color:{PALETTE['body']}">
    ¿Te gustaría activar alguna de estas funcionalidades? Habla con tu gestor de cuenta en Cifra.
  </p>
</div>

</body>
</html>"""


def _render_pdf(html: str, output_path: Path) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    try:
        import weasyprint
        weasyprint.HTML(string=html).write_pdf(str(output_path))
        return True
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["weasyprint", str(html_path), str(output_path)],
            capture_output=True, timeout=60,
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    print(f"  [WARN] WeasyPrint unavailable — HTML saved to {html_path}")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Cifra competitor monitor")
    parser.add_argument("--client-slug", required=True, help="Client slug in DB")
    parser.add_argument("--dry-run", action="store_true", help="Skip network calls")
    args = parser.parse_args()

    db.init_db()

    client = db.get_client(args.client_slug)
    if not client:
        print(f"ERROR: Client '{args.client_slug}' not found in DB.")
        sys.exit(1)

    tier = (client.get("tier") or "").lower()
    if tier not in ELIGIBLE_TIERS:
        print(f"ERROR: Competitor monitoring requires pro tier or above. Client tier: '{tier}'")
        sys.exit(1)

    competitors = db.list_competitors(args.client_slug)
    if not competitors:
        print(f"No competitors registered for '{args.client_slug}'. Add them with db.add_competitor().")
        sys.exit(0)

    competitors = competitors[:5]
    api_key = os.getenv("PAGESPEED_API_KEY")
    month_label = datetime.now().strftime("%B %Y")
    now_str = datetime.now().strftime("%Y-%m")

    print(f"\nScanning {len(competitors)} competitor(s) for {client.get('business_name', args.client_slug)}…\n")

    scan_results = []
    for comp in competitors:
        scan_data = _scan_competitor(comp, api_key, args.dry_run)
        prev_scan = db.get_last_competitor_scan(comp["id"])
        diff = _diff_scan(scan_data, prev_scan)
        scan_results.append({"competitor": comp, "scan": scan_data, "diff": diff})

        if not args.dry_run:
            db.log_competitor_scan(comp["id"], scan_data)

    output_path = PROJECT_ROOT / "output" / "competitor_reports" / args.client_slug / f"competitive_{now_str}.pdf"

    print(f"\nGenerating PDF report…")
    html = _build_html(client, scan_results, month_label)
    pdf_ok = _render_pdf(html, output_path)

    if pdf_ok and not args.dry_run:
        # Back-fill the report path on the latest scan rows
        for comp in competitors:
            last = db.get_last_competitor_scan(comp["id"])
            if last:
                with db._connect() as conn:
                    conn.execute(
                        "UPDATE competitor_scans SET report_pdf_path = ? WHERE id = ?",
                        (str(output_path), last["id"]),
                    )

    print(f"\nDone. Report: {output_path}")

    summary = {
        "client": args.client_slug,
        "month": now_str,
        "competitors_scanned": len(scan_results),
        "new_pages_detected": sum(len(r["diff"].get("new_pages", [])) for r in scan_results),
        "pricing_changes": sum(1 for r in scan_results if r["diff"].get("pricing_changed")),
        "report_pdf": str(output_path) if pdf_ok else None,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
