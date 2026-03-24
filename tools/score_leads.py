"""
score_leads.py

Usage:
    python tools/score_leads.py

Reads output/leads_master.csv, scores every lead on conversion likelihood,
and outputs the top 30 to output/leads_selected.csv with a Score and Reason
column.

Scoring priority: no_website > broken > redirected. Within each group,
leads with a phone number, physical address, and a real (non-chain) business
name score higher.
"""

import sys
import io
import csv
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Known chains / franchises / generic names to deprioritize
# ---------------------------------------------------------------------------

CHAIN_KEYWORDS = [
    "sfera", "amazon", "ka international", "zara", "mango", "h&m",
    "primark", "pull&bear", "bershka", "stradivarius", "massimo dutti",
]


def is_chain(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in CHAIN_KEYWORDS)


def has_phone(phone: str) -> bool:
    return bool(phone and phone.strip())


def has_address(address: str) -> bool:
    return bool(address and len(address.strip()) > 5)


def score_lead(row: dict) -> tuple[int, str]:
    """Return (score, reason) for a single lead."""
    score = 0
    reasons = []

    # --- Website status (max 50) ---
    status = row.get("Website Status", "").strip()
    if status == "no_website":
        score += 50
        reasons.append("no website (highest need)")
    elif status == "broken_website":
        score += 30
        reasons.append("broken website")
    elif status == "redirected_domain":
        score += 10
        reasons.append("redirected domain")

    # --- Phone (max 20) ---
    phone = row.get("Phone", "")
    if has_phone(phone):
        score += 20
        reasons.append("has phone")
    else:
        reasons.append("no phone (-20)")

    # --- Address (max 15) ---
    address = row.get("Address", "")
    if has_address(address):
        score += 15
        reasons.append("has address")
    else:
        reasons.append("no address (-15)")

    # --- Real business name (max 15) ---
    name = row.get("Business Name", "")
    if name and not is_chain(name):
        score += 15
        reasons.append("independent business")
    else:
        reasons.append("chain/franchise (-15)")

    return score, "; ".join(reasons)


def main():
    input_path = Path("output/leads_master.csv")
    output_path = Path("output/leads_selected.csv")

    if not input_path.exists():
        print(f"Error: {input_path} not found.")
        sys.exit(1)

    # Read all leads
    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        leads = list(reader)

    print(f"Loaded {len(leads)} leads from {input_path}")

    # Score each lead
    scored = []
    for row in leads:
        s, reason = score_lead(row)
        row["Score"] = s
        row["Reason"] = reason
        scored.append(row)

    # Sort by score descending, then by name for deterministic ordering
    scored.sort(key=lambda r: (-r["Score"], r.get("Business Name", "")))

    # Select top 30
    selected = scored[:30]

    # Print summary
    print(f"\nScoring distribution (all {len(scored)} leads):")
    score_dist = {}
    for r in scored:
        s = r["Score"]
        score_dist[s] = score_dist.get(s, 0) + 1
    for s in sorted(score_dist.keys(), reverse=True):
        print(f"  Score {s:3d}: {score_dist[s]} leads")

    print(f"\nSelected top 30:")
    for i, row in enumerate(selected, 1):
        print(f"  {i:2d}. [{row['Score']}] {row['Business Name']}")

    # Write output
    out_fields = list(fieldnames) + ["Score", "Reason"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for row in selected:
            writer.writerow(row)

    print(f"\n[OK] Saved {len(selected)} leads to {output_path}")


if __name__ == "__main__":
    main()
