---
name: change-request-quote
description: Use when the operator describes changes a client wants to make to their existing website or service. Generates a professional quote in Spanish with itemized pricing, checks what is already included in the client's current tier, and logs the request to the client database.
argument-hint: "[client-slug] [change description in natural language]"
---

# change-request-quote

Generates a structured, professional quote for website change requests — in Spanish, with tier-aware pricing and an auto-generated PDF.

## When to Invoke

Trigger this skill whenever:
- The operator describes work a client wants done ("el cliente quiere...", "añadir...", "modificar...")
- The operator asks for a quote or says "presupuesto de cambios"
- The operator says "cuánto costaría" for any discrete change item
- The work described is outside the client's current monthly retainer

Always check the client's tier in the DB **before** pricing anything.

---

## Workflow

### Step 1 — Fetch Client Record

Run `tools/db.py` via Python to retrieve the client:

```python
import sys; sys.path.insert(0, "tools")
from db import get_client
client = get_client("client-slug")
# Returns dict with: business_name, tier, contact_email, etc.
# Returns None if slug not found → ask operator for correct slug
```

If `get_client()` returns `None`, stop and ask the operator for the correct client slug.

---

### Step 2 — Parse and Classify the Change Request

Read the operator's natural language description. Identify each discrete change item and map it to the catalog:

| Code | Spanish label | Applies to | Price |
|------|--------------|------------|-------|
| `cambio_menor` | Cambio menor | Text edit, image swap, small CSS tweak | €35 |
| `nueva_seccion` | Nueva sección | New section on an existing page | €180 |
| `pagina_nueva` | Página nueva | Whole new page (design + content) | €390 |
| `pack_imagenes_ia` | Pack imágenes IA | 5 AI-generated images | €75 |
| `traduccion` | Traducción | Translation, per page | €120 |
| `seo_avanzado` | SEO avanzado | Advanced SEO optimisation for one page | €320 |
| `integracion_externa` | Integración externa | CRM, email platform, third-party embed | min €250 |
| `custom` | Personalizado | Anything not in catalog → flag for manual pricing | TBD |

Classification rules:
- A single sentence can contain multiple items — split them
- "traducir todo al inglés" on a 3-page site → 3 × `traduccion`
- `integracion_externa` minimum is €250; price higher for complex CRMs
- `custom` items must be flagged clearly — do not invent a price

---

### Step 3 — Apply Tier Credits

Free monthly changes included per tier:

| Tier | Free changes/month |
|------|--------------------|
| `basic` | 0 |
| `pro` | 1 |
| `premium` | 3 |
| `enterprise` | 5 |

Apply credits to the **cheapest** items first (ascending unit_price order). Mark those items `included_in_tier: true` and set their effective subtotal to €0.

Compute:
- `subtotal_gross` = sum of all `unit_price × quantity` (before credits)
- `tier_credits_applied` = sum of subtotals of included items
- `subtotal_net` = `subtotal_gross − tier_credits_applied`
- `vat_21` = `subtotal_net × 0.21`
- `total` = `subtotal_net + vat_21`

---

### Step 4 — Build the Quote JSON

```json
{
  "client_slug": "acme",
  "client_name": "Acme S.L.",
  "tier": "pro",
  "quote_date": "2026-04-16",
  "quote_number": 1,
  "line_items": [
    {
      "code": "cambio_menor",
      "description_es": "Cambio de texto en sección hero",
      "quantity": 1,
      "unit_price": 35,
      "subtotal": 35,
      "included_in_tier": true
    },
    {
      "code": "pagina_nueva",
      "description_es": "Nueva página de blog",
      "quantity": 1,
      "unit_price": 390,
      "subtotal": 390,
      "included_in_tier": false
    },
    {
      "code": "traduccion",
      "description_es": "Traducción al inglés (1 página)",
      "quantity": 1,
      "unit_price": 120,
      "subtotal": 120,
      "included_in_tier": false
    }
  ],
  "subtotal_gross": 545,
  "tier_credits_applied": 35,
  "subtotal_net": 510,
  "vat_21": 107.10,
  "total": 617.10,
  "payment_terms_es": "50% al aprobar, 50% a la entrega",
  "estimated_delivery_days": 7
}
```

Auto-increment `quote_number`: count JSON files already in `output/quotes/{client_slug}/` and add 1.

`estimated_delivery_days` heuristic: `max(3, min(21, len(line_items)))`.

Save the JSON to:
```
output/quotes/{client_slug}/quote_{number}_{date}.json
```
Create the directory if it does not exist.

---

### Step 5 — Generate the PDF

```bash
python tools/generate_quote_pdf.py output/quotes/{client_slug}/quote_{number}_{date}.json
```

The tool saves the PDF to the same folder:
```
output/quotes/{client_slug}/quote_{number}_{date}.pdf
```

If WeasyPrint is not available it will fall back to HTML and print a warning.

---

### Step 6 — Log to Database

```python
from db import add_change_request

summary_es = "; ".join(li["description_es"] for li in quote["line_items"])
add_change_request(
    client_slug=quote["client_slug"],
    description_es=f"[Presupuesto #{quote['quote_number']}] {summary_es}",
    price=quote["subtotal_net"],
)
```

Note: the `change_requests` table status defaults to `'pending'`. When the client approves the quote, update status to `'in_progress'` via `tools/db.py`. When work is complete, update to `'completed'` and add a line item to `billing_history` via `log_billing()`.

---

### Step 7 — Print Operator Summary (Spanish)

Print a formatted summary to the terminal:

```
PRESUPUESTO GENERADO — Acme S.L. (Tier: PRO)
═══════════════════════════════════════════════════
Ítem                              Bruto    Incluido  Neto
──────────────────────────────────────────────────────────
Cambio de texto en sección hero   €35      SÍ        €0
Nueva página de blog              €390     NO        €390
Traducción al inglés (1 pág)      €120     NO        €120
──────────────────────────────────────────────────────────
Subtotal bruto                             €545
Créditos de tier (pro, 1 cambio)           -€35
Subtotal neto                              €510
IVA 21%                                    €107.10
TOTAL                                      €617.10

Condiciones: 50% al aprobar, 50% a la entrega
Entrega estimada: 7 días hábiles

📄 PDF: output/quotes/acme/quote_1_2026-04-16.pdf
```

---

## Edge Cases

- **Client not found:** Stop, print error, ask operator for correct slug.
- **`custom` items present:** Generate the quote with TBD for those items, print a warning asking operator to manually set the price before sending.
- **integracion_externa below €250:** Round up to €250 minimum automatically.
- **All items included in tier:** Total = €0 + IVA on €0. Still generate the PDF so the client has a record showing the work is covered.
- **Multiple items of same type:** Each is its own line item (e.g., 3 pages of translation = 3 rows, not 1 row with quantity 3) unless the operator explicitly groups them.
