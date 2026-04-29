---
name: commercial-proposal
description: Generate a commercial proposal PDF for a lead — cover, situation analysis, tier recommendation, phases, pricing, case studies — same styling as audit/quote PDFs
argument-hint: "--lead-id 42 [--tier pro]"
---

# Commercial Proposal

Generates a professional Propuesta Comercial PDF in Spanish for a specific lead or a freeform brief. Uses the same Copper (#C17A3A) / Linen (#F5EDD6) / Charcoal (#1A1410) palette and WeasyPrint pipeline as the audit and quote PDFs. Output goes to `output/proposals/{slug}/proposal_{date}.pdf`.

## When to Invoke

- User says "propuesta comercial", "commercial proposal", "generate proposal", "make a quote for a lead"
- User provides a `lead_id` or a brief description of a prospect
- A lead is in `in_conversation` status and needs a formal offer
- User asks to prepare something to close a deal

## Workflow

### Step 1 — Resolve lead data

With `lead_id`:
```bash
python tools/generate_proposal_pdf.py --lead-id 42 --tier pro
```

With free-form brief (no lead in DB):
```bash
python tools/generate_proposal_pdf.py --brief "Restaurante en Madrid, sin web" --tier basic
```

Available tiers: `basic` (690€ + 49€/mes), `pro` (1290€ + 89€/mes), `premium` (1990€ + 129€/mes), `enterprise` (3500€ + 199€/mes).

If the user doesn't specify a tier, recommend based on:
- `no_site` / `broken` + small business → `basic`
- `outdated` + established business → `pro`
- Multiple locations or higher score → `premium`

### Step 2 — Tool generates the PDF

The tool builds a 7-section HTML document and converts via WeasyPrint (fpdf2 fallback):
1. **Cover** — business name, date, Cifra branding, "PROPUESTA COMERCIAL"
2. **Situación actual** — website status framed as business cost/missed opportunity
3. **Tier propuesto** — feature comparison table for all 4 tiers, recommended one highlighted in copper
4. **Fases del proyecto** — 5-phase timeline table (Descubrimiento → Diseño → Desarrollo → Lanzamiento → Mantenimiento)
5. **Inversión** — pricing table with recommended tier highlighted
6. **Casos de éxito** — up to 3 project thumbnails from `output/websites/`
7. **Próximos pasos** — CTA + signature block

### Step 3 — Report and deliver

- Confirm PDF path: `output/proposals/{slug}/proposal_{date}.pdf`
- Tell the user they can attach it to an email or share it directly
- Suggest: "Send via `cold-outreach` or email it directly from your client."

## Edge Cases

- **WeasyPrint not installed**: Tool falls back to HTML output. Remind user to install WeasyPrint on Windows (requires GTK runtime) or view the HTML version in Chrome and print to PDF.
- **No output/websites/ case studies**: Placeholder cards are shown instead.
- **lead_id not found**: Exit with error — confirm lead exists via DB or switch to --brief mode.
- **Tier not specified**: Default to `basic` and note the recommendation in your response.
