"""
build_dashboard.py

Usage:
    python tools/build_dashboard.py

Reads data/clients.db and generates output/dashboard.html — a private static
page showing all active clients, MRR, audit status, and change requests.

Styled to match Cifra website quality:
  - Playfair Display headings + Plus Jakarta Sans body
  - Copper #C17A3A / Linen #F5EDD6 / Charcoal #1A1410 palette
  - AOS scroll reveals
  - Chart.js for revenue breakdown

NOT committed to git (listed in .gitignore).
"""

import sys
import json
from datetime import date, datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

try:
    from db import _connect
    _DB_OK = True
except ImportError:
    _DB_OK = False

# ---------------------------------------------------------------------------
# Colour constants (match website palette)
# ---------------------------------------------------------------------------

COPPER    = "#C17A3A"
COPPER_DK = "#8A5225"
COPPER_LT = "#D9944E"
LINEN     = "#F5EDD6"
LINEN_DK  = "#E8DBC0"
CHARCOAL  = "#1A1410"
CHARCOAL_MD = "#2C2018"
TEXT_BODY = "#4A3825"
WHITE     = "#FFFFFF"
RED_FLAG  = "#C0392B"

TIER_COLORS = {
    "basic":      ("#6B7280", WHITE),
    "pro":        (COPPER, WHITE),
    "premium":    (CHARCOAL, LINEN),
    "enterprise": ("#1a1a2e", "#D9944E"),
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_data() -> dict:
    """Pull all dashboard data from the database."""
    if not _DB_OK:
        print("[WARN] db module not available — generating empty dashboard.", file=sys.stderr)
        return {
            "clients": [], "change_requests": [], "billing_by_tier": {},
            "mrr": 0.0, "generated_at": datetime.now().isoformat()
        }

    with _connect() as conn:
        clients = conn.execute("""
            SELECT c.*,
                   a.scan_date as last_scan_date,
                   a.total_findings as last_total_findings,
                   a.high as last_high_findings
            FROM clients c
            LEFT JOIN (
                SELECT client_id, scan_date, total_findings, high,
                       ROW_NUMBER() OVER (PARTITION BY client_id ORDER BY scan_date DESC) as rn
                FROM audits
            ) a ON a.client_id = c.id AND a.rn = 1
            ORDER BY c.tier DESC, c.business_name
        """).fetchall()

        changes = conn.execute("""
            SELECT cr.*, c.business_name, c.slug
            FROM change_requests cr
            JOIN clients c ON cr.client_id = c.id
            WHERE cr.status = 'pending'
            ORDER BY cr.requested_at DESC
        """).fetchall()

        billing_by_tier = conn.execute("""
            SELECT c.tier,
                   SUM(c.monthly_hosting_fee + COALESCE(c.monthly_security_fee, 0)) as tier_mrr,
                   COUNT(*) as client_count
            FROM clients c
            GROUP BY c.tier
        """).fetchall()

    clients_list = [dict(r) for r in clients]
    changes_list = [dict(r) for r in changes]

    mrr = sum(
        (c.get("monthly_hosting_fee") or 0) + (c.get("monthly_security_fee") or 0)
        for c in clients_list
    )

    tier_data = {r["tier"]: {"mrr": r["tier_mrr"] or 0, "count": r["client_count"]}
                 for r in billing_by_tier}

    return {
        "clients": clients_list,
        "change_requests": changes_list,
        "billing_by_tier": tier_data,
        "mrr": round(mrr, 2),
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


# ---------------------------------------------------------------------------
# HTML components
# ---------------------------------------------------------------------------

def _tier_badge(tier: str) -> str:
    bg, fg = TIER_COLORS.get(tier, ("#888", WHITE))
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;'
        f'letter-spacing:0.06em;text-transform:uppercase;">{tier}</span>'
    )


def _client_row(c: dict) -> str:
    tier = c.get("tier", "basic")
    mrr = (c.get("monthly_hosting_fee") or 0) + (c.get("monthly_security_fee") or 0)
    next_billing = c.get("next_billing_date") or "—"
    last_scan = (c.get("last_scan_date") or "")[:10] or "Sin escaneo"
    high_findings = c.get("last_high_findings") or 0
    total_findings = c.get("last_total_findings") or 0

    findings_cell = ""
    if total_findings > 0:
        color = RED_FLAG if high_findings > 0 else COPPER
        icon = "⚠" if high_findings > 0 else "●"
        findings_cell = (
            f'<span style="color:{color};font-weight:700;">'
            f'{icon} {total_findings} ({high_findings} críticos)</span>'
        )
    else:
        findings_cell = '<span style="color:#888;">Sin hallazgos</span>'

    return f"""
    <tr data-aos="fade-up" style="border-bottom:1px solid {LINEN_DK};">
        <td style="padding:14px 12px;font-weight:600;color:{CHARCOAL};">
            {c.get('business_name','—')}
            <div style="font-size:10px;color:#888;margin-top:2px;">{c.get('slug','')}</div>
        </td>
        <td style="padding:14px 12px;">{_tier_badge(tier)}</td>
        <td style="padding:14px 12px;font-weight:700;color:{COPPER};">
            €{mrr:.0f}<span style="font-weight:400;font-size:10px;color:#888;">/mes</span>
        </td>
        <td style="padding:14px 12px;font-size:11px;color:{TEXT_BODY};">{next_billing}</td>
        <td style="padding:14px 12px;font-size:11px;color:{TEXT_BODY};">{last_scan}</td>
        <td style="padding:14px 12px;font-size:11px;">{findings_cell}</td>
    </tr>
    """


def _change_row(cr: dict) -> str:
    price = cr.get("price")
    price_str = f"€{price:.0f}" if price else "A presupuestar"
    requested = (cr.get("requested_at") or "")[:10]
    return f"""
    <tr style="border-bottom:1px solid {LINEN_DK};">
        <td style="padding:12px;font-weight:600;color:{CHARCOAL};">
            {cr.get('business_name','—')}
        </td>
        <td style="padding:12px;font-size:11px;color:{TEXT_BODY};">
            {cr.get('description_es','—')}
        </td>
        <td style="padding:12px;font-size:11px;color:{TEXT_BODY};">{requested}</td>
        <td style="padding:12px;font-weight:600;color:{COPPER};">{price_str}</td>
        <td style="padding:12px;">
            <span style="background:#FEF3C7;color:#92400E;font-size:10px;
                         padding:3px 8px;border-radius:12px;font-weight:600;">
                Pendiente
            </span>
        </td>
    </tr>
    """


# ---------------------------------------------------------------------------
# Full dashboard HTML
# ---------------------------------------------------------------------------

def build_html(data: dict) -> str:
    clients  = data["clients"]
    changes  = data["change_requests"]
    tier_data = data["billing_by_tier"]
    mrr      = data["mrr"]
    gen_at   = data["generated_at"]

    annual_projection = mrr * 12
    client_count = len(clients)

    client_rows = "".join(_client_row(c) for c in clients) or \
        f'<tr><td colspan="6" style="padding:24px;text-align:center;color:#888;">Sin clientes registrados.</td></tr>'

    change_rows = "".join(_change_row(cr) for cr in changes) or \
        f'<tr><td colspan="5" style="padding:24px;text-align:center;color:#888;">Sin solicitudes pendientes.</td></tr>'

    # Chart.js data for tier breakdown
    tier_labels = json.dumps([t.upper() for t in tier_data.keys()])
    tier_mrr_vals = json.dumps([round(v["mrr"], 2) for v in tier_data.values()])
    tier_chart_colors = json.dumps([
        TIER_COLORS.get(t, ("#888", WHITE))[0] for t in tier_data.keys()
    ])

    google_fonts = (
        "https://fonts.googleapis.com/css2?"
        "family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&"
        "family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap"
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Panel de Control — Cifra</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{google_fonts}" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/aos@2.3.1/dist/aos.css">
<style>
:root {{
  --copper:     {COPPER};
  --copper-dk:  {COPPER_DK};
  --copper-lt:  {COPPER_LT};
  --linen:      {LINEN};
  --linen-dk:   {LINEN_DK};
  --charcoal:   {CHARCOAL};
  --text-body:  {TEXT_BODY};
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  background: var(--linen);
  color: var(--charcoal);
  min-height: 100vh;
}}

/* Header */
.header {{
  background: var(--charcoal);
  color: var(--linen);
  padding: 20px 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 3px solid var(--copper);
}}
.wordmark {{
  font-family: 'Playfair Display', serif;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: white;
}}
.wordmark span {{
  display: block;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 9px;
  letter-spacing: 0.18em;
  color: var(--copper-lt);
  font-weight: 600;
  margin-top: 1px;
}}
.header-meta {{ font-size: 11px; color: var(--linen-dk); text-align: right; }}
.header-meta strong {{ color: white; }}

/* KPI strip */
.kpi-strip {{
  display: flex;
  gap: 0;
  background: white;
  border-bottom: 2px solid var(--linen-dk);
}}
.kpi {{
  flex: 1;
  padding: 24px 32px;
  border-right: 1px solid var(--linen-dk);
  text-align: center;
}}
.kpi:last-child {{ border-right: none; }}
.kpi-value {{
  font-family: 'Playfair Display', serif;
  font-size: 34px;
  font-weight: 700;
  color: var(--copper);
  line-height: 1;
}}
.kpi-label {{
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--text-body);
  margin-top: 6px;
  text-transform: uppercase;
}}

/* Main content */
.main {{ max-width: 1200px; margin: 0 auto; padding: 40px 24px 80px; }}

/* Section title */
.section-title {{
  font-family: 'Playfair Display', serif;
  font-size: 22px;
  color: var(--charcoal);
  margin: 40px 0 16px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--copper);
  display: flex;
  align-items: baseline;
  gap: 12px;
}}
.section-count {{
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 12px;
  color: var(--copper);
  font-weight: 600;
}}

/* Tables */
.data-table {{
  width: 100%;
  border-collapse: collapse;
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 20px rgba(193,122,58,0.06);
}}
.data-table thead tr {{
  background: var(--charcoal);
  color: var(--linen);
}}
.data-table thead th {{
  padding: 12px 12px;
  text-align: left;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}}
.data-table tbody tr:hover {{
  background: rgba(193,122,58,0.04);
  transition: background 0.15s;
}}

/* Chart section */
.chart-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-top: 16px;
}}
.chart-card {{
  background: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 20px rgba(193,122,58,0.06);
}}
.chart-card h3 {{
  font-family: 'Playfair Display', serif;
  font-size: 15px;
  color: var(--charcoal);
  margin-bottom: 16px;
}}

/* Privacy notice */
.privacy-notice {{
  margin-top: 48px;
  padding: 12px 20px;
  background: rgba(193,122,58,0.08);
  border-left: 3px solid var(--copper);
  font-size: 11px;
  color: var(--text-body);
  border-radius: 0 6px 6px 0;
}}

@media (max-width: 768px) {{
  .chart-grid {{ grid-template-columns: 1fr; }}
  .kpi-strip {{ flex-wrap: wrap; }}
  .kpi {{ min-width: 50%; }}
  .header {{ padding: 16px 20px; }}
  .main {{ padding: 24px 16px 60px; }}
}}
</style>
</head>
<body>

<!-- HEADER -->
<header class="header">
  <div>
    <div class="wordmark">Cifra</div>
    <div style="font-size:14px;color:var(--copper-lt);font-family:'Playfair Display',serif;
                font-style:italic;margin-top:4px;">Panel de Control</div>
  </div>
  <div class="header-meta">
    <div><strong>Actualizado:</strong> {gen_at}</div>
    <div style="margin-top:4px;"><strong>{client_count}</strong> clientes activos</div>
    <div style="margin-top:4px;color:rgba(255,255,255,0.4);font-size:9px;">
      DOCUMENTO PRIVADO — NO DISTRIBUIR
    </div>
  </div>
</header>

<!-- KPI STRIP -->
<div class="kpi-strip" data-aos="fade-down">
  <div class="kpi">
    <div class="kpi-value">€{mrr:,.0f}</div>
    <div class="kpi-label">MRR Actual</div>
  </div>
  <div class="kpi">
    <div class="kpi-value">€{annual_projection:,.0f}</div>
    <div class="kpi-label">Proyección Anual</div>
  </div>
  <div class="kpi">
    <div class="kpi-value">{client_count}</div>
    <div class="kpi-label">Clientes Activos</div>
  </div>
  <div class="kpi">
    <div class="kpi-value">{len(changes)}</div>
    <div class="kpi-label">Cambios Pendientes</div>
  </div>
</div>

<div class="main">

  <!-- CLIENTS TABLE -->
  <div class="section-title" data-aos="fade-right">
    Cartera de Clientes
    <span class="section-count">{client_count} registros</span>
  </div>

  <div data-aos="fade-up">
    <table class="data-table">
      <thead>
        <tr>
          <th>Cliente</th>
          <th>Tier</th>
          <th>MRR</th>
          <th>Próxima Factura</th>
          <th>Último Escaneo</th>
          <th>Hallazgos Abiertos</th>
        </tr>
      </thead>
      <tbody>
        {client_rows}
      </tbody>
    </table>
  </div>

  <!-- CHANGE REQUESTS -->
  <div class="section-title" data-aos="fade-right">
    Cola de Cambios Pendientes
    <span class="section-count">{len(changes)} pendientes</span>
  </div>

  <div data-aos="fade-up">
    <table class="data-table">
      <thead>
        <tr>
          <th>Cliente</th>
          <th>Descripción</th>
          <th>Solicitado</th>
          <th>Precio</th>
          <th>Estado</th>
        </tr>
      </thead>
      <tbody>
        {change_rows}
      </tbody>
    </table>
  </div>

  <!-- REVENUE BREAKDOWN -->
  <div class="section-title" data-aos="fade-right">
    Desglose de Ingresos por Tier
  </div>

  <div class="chart-grid">
    <div class="chart-card" data-aos="fade-up">
      <h3>MRR por Tier</h3>
      <canvas id="tierDonut" height="220"></canvas>
    </div>
    <div class="chart-card" data-aos="fade-up" data-aos-delay="100">
      <h3>Clientes por Tier</h3>
      <canvas id="tierBar" height="220"></canvas>
    </div>
  </div>

  <!-- PRIVACY NOTICE -->
  <div class="privacy-notice" data-aos="fade-up">
    <strong>Aviso de privacidad:</strong> Este panel contiene datos personales y comerciales
    protegidos bajo el RGPD. No debe compartirse ni publicarse. Acceso restringido al equipo
    de Cifra.
  </div>

</div>

<script src="https://unpkg.com/aos@2.3.1/dist/aos.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
AOS.init({{ duration: 700, easing: 'ease-out-cubic', once: true }});

const tierLabels = {tier_labels};
const tierMrr    = {tier_mrr_vals};
const tierColors = {tier_chart_colors};
const clientCounts = {json.dumps([v.get('count', 0) for v in tier_data.values()])};

const fontConfig = {{
  family: "'Plus Jakarta Sans', sans-serif",
  size: 11,
  color: '{TEXT_BODY}',
}};

Chart.defaults.font.family = fontConfig.family;
Chart.defaults.font.size   = fontConfig.size;
Chart.defaults.color       = fontConfig.color;

new Chart(document.getElementById('tierDonut'), {{
  type: 'doughnut',
  data: {{
    labels: tierLabels,
    datasets: [{{
      data: tierMrr,
      backgroundColor: tierColors,
      borderWidth: 2,
      borderColor: '{WHITE}',
    }}],
  }},
  options: {{
    plugins: {{
      legend: {{ position: 'right' }},
      tooltip: {{
        callbacks: {{
          label: ctx => ' €' + ctx.parsed.toFixed(0) + '/mes',
        }},
      }},
    }},
    cutout: '60%',
  }},
}});

new Chart(document.getElementById('tierBar'), {{
  type: 'bar',
  data: {{
    labels: tierLabels,
    datasets: [{{
      label: 'Clientes',
      data: clientCounts,
      backgroundColor: tierColors,
      borderRadius: 6,
      borderSkipped: false,
    }}],
  }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{
        beginAtZero: true,
        ticks: {{ stepSize: 1 }},
        grid: {{ color: 'rgba(0,0,0,0.04)' }},
      }},
      x: {{ grid: {{ display: false }} }},
    }},
  }},
}});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_dashboard() -> Path:
    data = _load_data()
    html = build_html(data)
    out_path = PROJECT_ROOT / "output" / "dashboard.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[OK] Dashboard saved: {out_path}", file=sys.stderr)
    return out_path


if __name__ == "__main__":
    build_dashboard()
