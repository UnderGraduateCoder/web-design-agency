"""
pdf_engine.py — Unified PDF renderer for Cifra.

render_pdf(html_string, output_path) tries in order:
  1. WeasyPrint (best quality — needs GTK3 on Windows)
  2. Playwright Chromium (headless, no system deps)
  3. fpdf2 plain-text fallback (last resort)

Usage:
    from tools.pdf_engine import render_pdf
    out = render_pdf(html_str, Path("output/report.pdf"))
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ENGINE_USED: str = "unknown"


def render_pdf(html_string: str, output_path: str | Path) -> Path:
    """Render html_string to a PDF at output_path. Returns the Path written."""
    global ENGINE_USED
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # --- Attempt 1: WeasyPrint ---
    try:
        import weasyprint
        weasyprint.HTML(string=html_string).write_pdf(str(out))
        ENGINE_USED = "weasyprint"
        return out
    except Exception:
        pass

    # --- Attempt 2: Playwright Chromium ---
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.set_content(html_string, wait_until="networkidle")
            page.pdf(
                path=str(out),
                format="A4",
                margin={"top": "20mm", "bottom": "20mm", "left": "18mm", "right": "18mm"},
                print_background=True,
            )
            browser.close()
        ENGINE_USED = "playwright"
        return out
    except Exception as e:
        print(f"[pdf_engine] Playwright failed: {e}", file=sys.stderr)

    # --- Attempt 3: Save as HTML (always works) ---
    html_out = out.with_suffix(".html")
    html_out.write_text(html_string, encoding="utf-8")
    ENGINE_USED = "html_fallback"
    print(
        f"[pdf_engine] All PDF engines failed — saved as HTML: {html_out}",
        file=sys.stderr,
    )
    return html_out


def active_engine() -> str:
    """Return name of the engine that last succeeded."""
    return ENGINE_USED
