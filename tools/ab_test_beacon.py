"""
A/B test beacon — Flask event receiver.

Run:
    python tools/ab_test_beacon.py

Listens on AB_BEACON_PORT (default 5050).
Receives pageview/conversion events from deployed A/B test snippets.
Logs events to ab_test_events table.
Auto-promotes the winning variant after 14 days OR 1000 unique visitors.
Generates a Spanish PDF report on promotion.

Endpoints:
    POST /beacon   — receive an event
    GET  /health   — health check
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("ERROR: Flask is required. Run: pip install flask")
    sys.exit(1)

def _load_db():
    spec = _ilu.spec_from_file_location("db", PROJECT_ROOT / "tools" / "db.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

db = _load_db()
db.init_db()

app = Flask(__name__)

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
# Report generation
# ---------------------------------------------------------------------------

def _conversion_rate(events: list, variant: str) -> float:
    views = sum(1 for e in events if e["variant"] == variant and e["event_type"] == "pageview")
    convs = sum(1 for e in events if e["variant"] == variant and e["event_type"] == "conversion")
    return convs / views if views > 0 else 0.0


def _determine_winner(events: list) -> str:
    cr_a = _conversion_rate(events, "A")
    cr_b = _conversion_rate(events, "B")
    if abs(cr_a - cr_b) < 0.02:
        return "A"  # tie → keep A
    return "A" if cr_a >= cr_b else "B"


def _unique_visitors(events: list) -> int:
    return len(set(
        e["session_id"] for e in events
        if e["event_type"] == "pageview" and e["session_id"]
    ))


def _build_report_html(test: dict, events: list, winner: str, client: dict) -> str:
    client_name = client.get("business_name") or client.get("slug", "Cliente")
    test_name = test.get("test_name", f"Test #{test['id']}")
    title = f"Informe A/B — {test_name} — {client_name}"

    started = datetime.fromisoformat(test["started_at"]) if test.get("started_at") else datetime.now()
    ended = datetime.now()
    duration_days = (ended - started).days

    cr_a = _conversion_rate(events, "A")
    cr_b = _conversion_rate(events, "B")
    total_visitors = _unique_visitors(events)
    views_a = sum(1 for e in events if e["variant"] == "A" and e["event_type"] == "pageview")
    views_b = sum(1 for e in events if e["variant"] == "B" and e["event_type"] == "pageview")
    convs_a = sum(1 for e in events if e["variant"] == "A" and e["event_type"] == "conversion")
    convs_b = sum(1 for e in events if e["variant"] == "B" and e["event_type"] == "conversion")

    lift = ((cr_b - cr_a) / cr_a * 100) if cr_a > 0 else 0
    is_tie = abs(cr_a - cr_b) < 0.02

    winner_label = "Empate (se mantiene Variante A)" if is_tie else f"Variante {winner}"
    winner_color = PALETTE["orange"] if is_tie else PALETTE["green"]

    lift_str = f"+{lift:.1f}%" if lift > 0 else f"{lift:.1f}%"
    lift_color = PALETTE["green"] if lift > 0 else PALETTE["red"]

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

<div style="background:{PALETTE['charcoal']};padding:32px 0 20px;margin:-20mm -18mm 0;padding-left:18mm;padding-right:18mm;border-bottom:4px solid {PALETTE['copper']}">
  <p style="font-size:10px;letter-spacing:0.15em;text-transform:uppercase;color:{PALETTE['copper']};margin-bottom:8px">Cifra Web Agency</p>
  <h1 style="font-size:22px;color:{PALETTE['white']};line-height:1.3">{title}</h1>
  <p style="font-size:11px;color:#aaa;margin-top:8px">
    {started.strftime('%d/%m/%Y')} → {ended.strftime('%d/%m/%Y')} · {duration_days} días · {total_visitors} visitantes únicos
  </p>
</div>

<div style="background:{PALETTE['linen']};padding:16px 0;margin:0 -18mm;padding-left:18mm;padding-right:18mm;border-bottom:1px solid {PALETTE['linen_dk']};display:flex;gap:0">
  {"".join(f'<div style="flex:1;text-align:center;border-right:1px solid {PALETTE["linen_dk"]}"><p style="font-family:Playfair Display,serif;font-size:28px;color:{c};font-weight:700">{v}</p><p style="font-size:9px;text-transform:uppercase;letter-spacing:0.1em;color:{PALETTE["body"]}">{l}</p></div>' for v, l, c in [(total_visitors, "Visitantes", PALETTE["copper"]), (f"{cr_a*100:.1f}%", "Conv. Variante A", PALETTE["body"]), (f"{cr_b*100:.1f}%", "Conv. Variante B", PALETTE["body"]), (lift_str, "Lift", lift_color)])}
</div>

<div style="margin-top:28px;text-align:center;padding:24px;border:2px solid {winner_color};border-radius:8px">
  <p style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{PALETTE['body']};margin-bottom:8px">Variante Ganadora</p>
  <p style="font-family:'Playfair Display',serif;font-size:32px;font-weight:700;color:{winner_color}">{winner_label}</p>
  {'<p style="margin-top:8px;font-size:12px;color:'+PALETTE["body"]+'">Sin diferencia estadísticamente relevante (&lt;2pp). Se mantiene la variante A por defecto.</p>' if is_tie else ''}
</div>

<div style="margin-top:28px">
  <h2 style="font-size:15px;color:{PALETTE['charcoal']};padding-left:10px;border-left:4px solid {PALETTE['copper']};margin-bottom:12px">Resultados por Variante</h2>
  <table style="width:100%;border-collapse:collapse;font-size:12px">
    <thead>
      <tr style="background:{PALETTE['linen_dk']}">
        <th style="padding:10px 12px;text-align:left">Variante</th>
        <th style="padding:10px 12px;text-align:center">Visitas</th>
        <th style="padding:10px 12px;text-align:center">Conversiones</th>
        <th style="padding:10px 12px;text-align:center">Tasa de Conv.</th>
      </tr>
    </thead>
    <tbody>
      <tr style="{'background:'+PALETTE['linen'] if winner == 'A' and not is_tie else ''}">
        <td style="padding:10px 12px;border-bottom:1px solid {PALETTE['linen_dk']}">Variante A {'✓' if winner == 'A' else ''}</td>
        <td style="padding:10px 12px;border-bottom:1px solid {PALETTE['linen_dk']};text-align:center">{views_a}</td>
        <td style="padding:10px 12px;border-bottom:1px solid {PALETTE['linen_dk']};text-align:center">{convs_a}</td>
        <td style="padding:10px 12px;border-bottom:1px solid {PALETTE['linen_dk']};text-align:center;font-weight:700">{cr_a*100:.1f}%</td>
      </tr>
      <tr style="{'background:'+PALETTE['linen'] if winner == 'B' and not is_tie else ''}">
        <td style="padding:10px 12px">Variante B {'✓' if winner == 'B' else ''}</td>
        <td style="padding:10px 12px;text-align:center">{views_b}</td>
        <td style="padding:10px 12px;text-align:center">{convs_b}</td>
        <td style="padding:10px 12px;text-align:center;font-weight:700">{cr_b*100:.1f}%</td>
      </tr>
    </tbody>
  </table>
</div>

<div style="margin-top:24px;padding:16px;background:{PALETTE['linen']};border-radius:6px;font-size:12px">
  <p style="font-weight:600;margin-bottom:6px">Metodología</p>
  <p>Asignación aleatoria 50/50 con stickiness por cookie (30 días). El test finalizó automáticamente al alcanzar
  {'14 días de duración' if duration_days >= 14 else '1.000 visitantes únicos'}. Umbral de empate: &lt;2 puntos porcentuales de diferencia.</p>
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
    app.logger.warning(f"WeasyPrint unavailable — HTML saved: {html_path}")
    return False


# ---------------------------------------------------------------------------
# Auto-promotion
# ---------------------------------------------------------------------------

def _check_auto_promote(test_id: int) -> None:
    test = db.get_ab_test(test_id)
    if not test or test["status"] != "running":
        return

    events = db.get_ab_test_events(test_id)
    unique = _unique_visitors(events)
    started = datetime.fromisoformat(test["started_at"]) if test.get("started_at") else datetime.now()
    days = (datetime.now() - started).days

    if unique < 1000 and days < 14:
        return

    winner = _determine_winner(events)
    db.end_ab_test(test_id, winner)
    app.logger.info(f"Test #{test_id} auto-promoted: winner={winner} visitors={unique} days={days}")

    try:
        client_slug = test.get("client_slug")
        if not client_slug:
            with db._connect() as conn:
                row = conn.execute(
                    "SELECT slug FROM clients WHERE id = (SELECT client_id FROM ab_tests WHERE id = ?)",
                    (test_id,),
                ).fetchone()
                client_slug = row["slug"] if row else "unknown"

        client = db.get_client(client_slug) or {}
        html = _build_report_html(test, events, winner, client)
        out_path = (
            PROJECT_ROOT / "output" / "ab_tests" / client_slug / f"{test_id}_report.pdf"
        )
        _render_pdf(html, out_path)
        app.logger.info(f"Report generated: {out_path}")
    except Exception as exc:
        app.logger.error(f"Report generation failed for test #{test_id}: {exc}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ab-test-beacon"})


@app.route("/beacon", methods=["POST"])
def beacon():
    try:
        data = request.get_json(force=True, silent=True) or {}
        test_id = data.get("test_id")
        client_slug = data.get("client_slug", "")
        variant = data.get("variant", "")
        event_type = data.get("event_type", "pageview")
        session_id = data.get("session_id", "")

        if not test_id or not variant:
            return jsonify({"error": "test_id and variant required"}), 400

        variant = variant.upper()
        if variant not in ("A", "B"):
            return jsonify({"error": "variant must be A or B"}), 400

        event_id = db.log_ab_event(
            test_id=int(test_id),
            client_slug=client_slug,
            variant=variant,
            event_type=event_type,
            session_id=str(session_id)[:255] if session_id else None,
        )

        _check_auto_promote(int(test_id))
        return jsonify({"ok": True, "event_id": event_id}), 200

    except Exception as exc:
        app.logger.error(f"Beacon error: {exc}")
        return jsonify({"error": "internal error"}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("AB_BEACON_PORT", 5050))
    print(f"AB Test Beacon listening on http://0.0.0.0:{port}")
    print(f"Health check: http://localhost:{port}/health")
    print(f"Beacon endpoint: http://localhost:{port}/beacon")
    app.run(host="0.0.0.0", port=port, debug=False)
