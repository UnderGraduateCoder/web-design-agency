"""
batch_build.py

Usage:
    python tools/batch_build.py
    python tools/batch_build.py --limit 5     # build only the first 5
    python tools/batch_build.py --budget 2.00  # set cost ceiling (default $1.50)

Reads output/leads_selected.csv and runs the full website pipeline for each
lead: gather_business_info → extract_brand → generate_images → find_hero_video
→ generate_copy → build_website. Saves each result to output/websites/{slug}.html.

Tracks Claude API token spend and stops if cumulative cost exceeds the budget.
"""

import sys
import io
import csv
import json
import os
import re
import subprocess
import argparse
import time
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Claude Sonnet 4.6 pricing (USD per token)
INPUT_PRICE_PER_TOKEN = 3.0 / 1_000_000   # $3 per million input tokens
OUTPUT_PRICE_PER_TOKEN = 15.0 / 1_000_000  # $15 per million output tokens

TOOLS_DIR = Path("tools")
TMP_DIR = Path(".tmp")
OUTPUT_DIR = Path("output")
WEBSITES_DIR = OUTPUT_DIR / "websites"
ASSETS_DIR = OUTPUT_DIR / "assets"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert business name to a safe, lowercase filename slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-") or "business"


def parse_tokens(output: str) -> tuple[int, int]:
    """Extract input/output token counts from subprocess output."""
    total_input = 0
    total_output = 0
    for line in output.split("\n"):
        if "[TOKENS]" in line:
            match = re.search(r"input=(\d+)\s+output=(\d+)", line)
            if match:
                total_input += int(match.group(1))
                total_output += int(match.group(2))
    return total_input, total_output


def calc_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate USD cost from token counts."""
    return input_tokens * INPUT_PRICE_PER_TOKEN + output_tokens * OUTPUT_PRICE_PER_TOKEN


def run_tool(cmd: list[str], timeout: int = 180) -> tuple[bool, str]:
    """Run a tool as a subprocess. Returns (success, stdout+stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(Path.cwd()),
        )
        output = result.stdout + "\n" + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    except Exception as e:
        return False, str(e)


def classify_business(name: str) -> dict:
    """Classify a textile business by name into specialty, scale, and customer type."""
    name_lower = name.lower()

    # Specialty detection
    specialty = "textile_general"
    specialty_label = "empresa textil"
    if any(w in name_lower for w in ["bordado", "bordados", "regisol"]):
        specialty = "embroidery"
        specialty_label = "taller especializado en bordados industriales y decorativos"
    elif any(w in name_lower for w in ["hilado", "hilados", "hilatura"]):
        specialty = "yarn_spinning"
        specialty_label = "empresa de hilados y fibras textiles"
    elif any(w in name_lower for w in ["confeccion", "confeccions", "costur", "corte y confección", "muestrario"]):
        specialty = "sewing_workshop"
        specialty_label = "taller de confección y patronaje textil"
    elif any(w in name_lower for w in ["hogar", "home", "ropa de cama", "dream home"]):
        specialty = "home_textiles"
        specialty_label = "empresa de textiles para el hogar y decoración"
    elif any(w in name_lower for w in ["acabado", "acabados", "cromia"]):
        specialty = "textile_finishing"
        specialty_label = "empresa de acabados y tratamientos textiles"
    elif any(w in name_lower for w in ["moda", "boutique", "le boutique"]):
        specialty = "fashion_retail"
        specialty_label = "tienda de moda y confección"
    elif "muestrario" in name_lower:
        specialty = "sample_making"
        specialty_label = "taller de muestrarios textiles"

    # Scale detection
    scale = "small_business"
    if any(s in name for s in ["S.L.", "S.L.U", "S.A.", "C.B.", "SL", " SA"]):
        scale = "company"
    elif any(w in name_lower for w in ["creacion", "costurero", " by "]) or _looks_like_personal_name(name):
        scale = "artisan"

    # Customer type
    customer_map = {
        "embroidery": "b2b", "textile_finishing": "b2b", "yarn_spinning": "b2b",
        "sample_making": "b2b", "fashion_retail": "b2c", "home_textiles": "b2c",
        "sewing_workshop": "mixed",
    }
    customer = customer_map.get(specialty, "mixed")

    return {
        "specialty": specialty,
        "specialty_label": specialty_label,
        "scale": scale,
        "customer_focus": customer,
    }


def _looks_like_personal_name(name: str) -> bool:
    """Heuristic: business name looks like a person's name (2-3 short words, no corporate suffixes)."""
    clean = re.sub(r"[,.]", "", name).strip()
    words = clean.split()
    if len(words) in (2, 3) and all(w[0].isupper() and w.isalpha() for w in words):
        corporate = ["textil", "moda", "hogar", "bordados", "confecciones", "hilados"]
        if not any(w.lower() in corporate for w in words):
            return True
    return False


def build_description(row: dict) -> str:
    """Construct an enriched business description from CSV row data."""
    name = row.get("Business Name", "").strip()
    address = row.get("Address", "").strip()
    phone = row.get("Phone", "").strip()

    classification = classify_business(name)
    label = classification["specialty_label"]
    customer = classification["customer_focus"]

    customer_desc = ""
    if customer == "b2b":
        customer_desc = " Orientado a profesionales del sector y empresas."
    elif customer == "b2c":
        customer_desc = " Orientado al cliente final y particulares."

    desc = f"{name}, {label} ubicada en {address}.{customer_desc}"
    if phone:
        desc += f" Teléfono: {phone}."
    return desc


def save_classification(name: str) -> dict:
    """Classify and save to .tmp for downstream tools to read."""
    classification = classify_business(name)
    cls_path = TMP_DIR / "business_classification.json"
    with open(cls_path, "w", encoding="utf-8") as f:
        json.dump(classification, f, ensure_ascii=False, indent=2)
    return classification


def adjust_asset_paths(html: str) -> str:
    """
    Adjust asset paths in HTML from assets/ to ../assets/
    since output/websites/ is one level deeper than output/.
    """
    # Match src="assets/...", url('assets/...'), href="assets/..."
    html = re.sub(r'(src|href)="assets/', r'\1="../assets/', html)
    html = re.sub(r"(src|href)='assets/", r"\1='../assets/", html)
    html = re.sub(r"url\('assets/", "url('../assets/", html)
    html = re.sub(r'url\("assets/', 'url("../assets/', html)
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch-build websites from selected leads.")
    parser.add_argument("--limit", type=int, default=30, help="Max websites to build (default 30)")
    parser.add_argument("--budget", type=float, default=1.50, help="Claude API budget ceiling in USD (default 1.50)")
    args = parser.parse_args()

    input_path = OUTPUT_DIR / "leads_selected.csv"
    if not input_path.exists():
        print(f"Error: {input_path} not found. Run tools/score_leads.py first.")
        sys.exit(1)

    # Read selected leads
    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        leads = list(reader)

    total_leads = min(len(leads), args.limit)
    print(f"{'='*60}")
    print(f"  BATCH WEBSITE BUILDER")
    print(f"  Leads: {total_leads}  |  Budget: ${args.budget:.2f}")
    print(f"{'='*60}\n")

    # Ensure output dirs exist
    WEBSITES_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(exist_ok=True)

    # Tracking
    cumulative_input_tokens = 0
    cumulative_output_tokens = 0
    completed = []
    failures = []
    stopped_early = False

    for i, row in enumerate(leads[:total_leads]):
        idx = i + 1
        name = row.get("Business Name", "Unknown").strip()
        slug = slugify(name)
        score = row.get("Score", "?")

        print(f"\n{'─'*60}")
        print(f"  [{idx}/{total_leads}] {name}  (score: {score})")
        print(f"{'─'*60}")

        step_input = 0
        step_output = 0
        step_failed = False
        fail_reason = ""

        # --- Step 0: Classify business and save for downstream tools ---
        classification = save_classification(name)
        print(f"  Type: {classification['specialty']} / {classification['scale']} / {classification['customer_focus']}")

        # --- Step 1: Gather business info ---
        description = build_description(row)
        print(f"  1/6 gather_business_info ... ", end="", flush=True)
        ok, output = run_tool([
            sys.executable, str(TOOLS_DIR / "gather_business_info.py"),
            description,
        ])
        if ok:
            inp, out = parse_tokens(output)
            step_input += inp
            step_output += out
            print(f"OK ({inp}+{out} tokens)")
        else:
            print(f"FAILED")
            step_failed = True
            fail_reason = "gather_business_info failed"
            # Print first error line for debugging
            for line in output.split("\n"):
                if "error" in line.lower() or "Error" in line:
                    print(f"    → {line.strip()}")
                    break

        if step_failed:
            failures.append({"name": name, "reason": fail_reason})
            continue

        # --- Step 2: Extract brand (optional, will fail gracefully for no_website) ---
        original_url = row.get("Original URL", "").strip()
        if original_url:
            print(f"  2/6 extract_brand ... ", end="", flush=True)
            ok, output = run_tool([
                sys.executable, str(TOOLS_DIR / "extract_brand.py"),
            ], timeout=30)
            print("OK" if ok else "skipped (no brand found)")
        else:
            print(f"  2/6 extract_brand ... skipped (no website)")

        # --- Step 3: Generate hero image (Gemini, free) ---
        print(f"  3/6 generate_images ... ", end="", flush=True)
        ok, output = run_tool([
            sys.executable, str(TOOLS_DIR / "generate_images.py"),
        ], timeout=120)
        if ok:
            print("OK")
        else:
            print("skipped (image gen failed)")

        # --- Step 4: Find hero video (Pexels, free) ---
        print(f"  4/6 find_hero_video ... ", end="", flush=True)
        ok, output = run_tool([
            sys.executable, str(TOOLS_DIR / "find_hero_video.py"),
        ], timeout=120)
        if ok:
            print("OK")
        else:
            print("skipped (video search failed)")

        # --- Step 5: Generate copy ---
        print(f"  5/6 generate_copy ... ", end="", flush=True)
        ok, output = run_tool([
            sys.executable, str(TOOLS_DIR / "generate_copy.py"),
        ])
        if ok:
            inp, out = parse_tokens(output)
            step_input += inp
            step_output += out
            print(f"OK ({inp}+{out} tokens)")
        else:
            print(f"FAILED")
            step_failed = True
            fail_reason = "generate_copy failed"
            for line in output.split("\n"):
                if "error" in line.lower() or "Error" in line:
                    print(f"    → {line.strip()}")
                    break

        if step_failed:
            failures.append({"name": name, "reason": fail_reason})
            continue

        # --- Step 6: Build website ---
        print(f"  6/6 build_website ... ", end="", flush=True)
        ok, output = run_tool([
            sys.executable, str(TOOLS_DIR / "build_website.py"),
        ])
        if ok:
            print("OK")
        else:
            print("FAILED")
            failures.append({"name": name, "reason": "build_website failed"})
            continue

        # --- Post-process: move to output/websites/{slug}.html ---
        src = OUTPUT_DIR / "index.html"
        if src.exists():
            html = src.read_text(encoding="utf-8")
            html = adjust_asset_paths(html)
            dest = WEBSITES_DIR / f"{slug}.html"
            dest.write_text(html, encoding="utf-8")
            print(f"  → Saved: {dest}")
        else:
            print(f"  → Warning: output/index.html not found after build")
            failures.append({"name": name, "reason": "index.html missing after build"})
            continue

        # Update cumulative tokens
        cumulative_input_tokens += step_input
        cumulative_output_tokens += step_output
        step_cost = calc_cost(step_input, step_output)
        total_cost = calc_cost(cumulative_input_tokens, cumulative_output_tokens)

        completed.append({
            "name": name,
            "slug": slug,
            "cost": step_cost,
            "file": str(dest),
        })

        print(f"  Cost: ${step_cost:.4f}  |  Cumulative: ${total_cost:.4f}")

        # --- Every 5 websites: cost checkpoint ---
        if idx % 5 == 0:
            print(f"\n  {'='*50}")
            print(f"  CHECKPOINT: {idx} websites completed")
            print(f"  Cumulative Claude cost: ${total_cost:.4f}")
            print(f"  Budget remaining: ${args.budget - total_cost:.4f}")
            print(f"  {'='*50}")

            if total_cost > args.budget:
                print(f"\n  ⚠ BUDGET EXCEEDED (${total_cost:.4f} > ${args.budget:.2f})")
                print(f"  Stopping after {idx} websites.")
                stopped_early = True
                break

    # --- Final report ---
    total_cost = calc_cost(cumulative_input_tokens, cumulative_output_tokens)
    print(f"\n{'='*60}")
    print(f"  BATCH BUILD {'STOPPED EARLY' if stopped_early else 'COMPLETE'}")
    print(f"{'='*60}")
    print(f"  Websites generated : {len(completed)} / {total_leads}")
    print(f"  Total Claude cost  : ${total_cost:.4f}")
    print(f"    Input tokens     : {cumulative_input_tokens:,}")
    print(f"    Output tokens    : {cumulative_output_tokens:,}")
    print(f"  Failures           : {len(failures)}")
    if failures:
        for f in failures:
            print(f"    - {f['name']}: {f['reason']}")
    print(f"  Output directory   : {WEBSITES_DIR}/")
    print(f"{'='*60}")

    # Open best result in browser (first completed)
    if completed:
        best = completed[0]["file"]
        print(f"\nOpening {best} in browser...")
        os.system(f'start "" "{best}"')


if __name__ == "__main__":
    main()
