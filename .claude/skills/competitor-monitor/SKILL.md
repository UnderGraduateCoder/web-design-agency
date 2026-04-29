---
name: competitor-monitor
description: Monthly competitive intelligence scan for pro+ clients — captures competitor keywords, pricing, new pages, and PageSpeed scores, then generates a Spanish PDF report with upsell hooks.
version: 1.0.0
triggers: [/competitor-monitor]
argument-hint: "[client_slug] [competitor_url_1] ... [competitor_url_5]"
---

# Skill: competitor-monitor

Generates a monthly competitive intelligence PDF in Spanish for a client, titled  
**"Inteligencia Competitiva — {cliente} — {mes}"**.

## Tier requirement

**Pro, Premium, or Enterprise only.** Reject invocation for clients on the basic tier — check `db.get_client(slug)["tier"]` before proceeding.

## When to invoke

MUST invoke when the user:
- Asks to scan or monitor a client's competitors
- Requests an "informe competitivo" or "inteligencia competitiva"
- Uses phrases like "monitorear competencia", "competidores", "qué hacen los competidores"
- Asks to add a competitor URL for a client

## Setup: Registering competitors

Before the first scan, competitors must be registered in the DB:

```python
import tools.db as db
db.add_competitor("client-slug", "https://competitor1.com")
db.add_competitor("client-slug", "https://competitor2.com")
# up to 5 per client
```

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `PAGESPEED_API_KEY` | Optional | PageSpeed Insights scores (free tier). Without it, performance section shows N/D. |

Get a free API key at: https://developers.google.com/speed/docs/insights/v5/get-started

## Usage

```bash
# Standard monthly run
python tools/monitor_competitors.py --client-slug <slug>

# Dry run (no network calls, no DB writes)
python tools/monitor_competitors.py --client-slug <slug> --dry-run
```

## What is scanned per competitor

| Data point | How |
|---|---|
| Meta keywords | `<meta name="keywords">` |
| Page title + H1s | HTML parsing |
| Visible pricing | Regex for €/$/£ patterns |
| Internal pages | `<a href>` extraction |
| Services page content | Tries /servicios, /services, /precios |
| PageSpeed scores | Google API (mobile, performance + SEO + accessibility) |
| New pages since last scan | Diff against previous `competitor_scans` DB row |

## PDF output

**Location:** `output/competitor_reports/{slug}/competitive_{YYYY-MM}.pdf`

**Sections:**
1. KPI strip — # competitors, with pricing, with new pages, errors
2. Resumen Ejecutivo — plain Spanish summary paragraph
3. Comparativa de Rendimiento — PageSpeed scores side-by-side table
4. Actividad Detectada — per-competitor breakdown (keywords, prices, new pages)
5. Oportunidades de Upsell — 8 Cifra differentiators the competitors lack

**Design:** matches audit/quote PDF design language (Copper palette, Playfair Display / Plus Jakarta Sans, WeasyPrint HTML with fpdf2 fallback).

## DB logging

Every scan is logged to `competitor_scans` via `db.log_competitor_scan()`.  
The `report_pdf_path` column is back-filled after PDF generation.

## Monthly automation

`tools/run_monthly_audits.py` automatically calls `monitor_competitors.py` for all pro+ clients after their security audit completes.

## Agent workflow

1. Confirm client exists and tier is pro/premium/enterprise
2. If no competitors registered: call `db.add_competitor()` for each URL provided by the user
3. Run `python tools/monitor_competitors.py --client-slug <slug>`
4. Report output PDF path and highlight any pricing changes or new pages detected
