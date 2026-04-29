"""
calculate_audit_price.py

Usage:
    python tools/calculate_audit_price.py <findings.json> [--tier basic|pro|premium|enterprise]

Reads a findings.json produced by security_audit.py and returns a structured
price quote as JSON. Can also be imported and called directly.

Output schema:
    {
        "line_items": [
            {"description": "...", "quantity": N, "unit_price": X, "subtotal": Y}
        ],
        "subtotal": X,
        "discount_pct": 0|15|25,
        "discount_amount": X,
        "remediation_total": X,
        "monthly_monitoring": X,
        "currency": "EUR"
    }
"""

import sys
import json
import argparse
from pathlib import Path

# Per-severity unit prices (EUR)
PRICE_HIGH   = 250.0
PRICE_MEDIUM = 120.0
PRICE_LOW    =  50.0

# Monthly monitoring rates by tier (EUR/month)
MONITORING_RATES = {
    "basic":      79.0,
    "pro":       149.0,
    "premium":   199.0,
    "enterprise": 299.0,
}

# Volume discount thresholds
DISCOUNT_TIER_1_THRESHOLD = 10   # >10 total findings → 15%
DISCOUNT_TIER_2_THRESHOLD = 20   # >20 total findings → 25%
DISCOUNT_TIER_1_PCT = 15
DISCOUNT_TIER_2_PCT = 25


def calculate(findings: dict | list, tier: str = "basic") -> dict:
    """
    Accept either a findings dict (with 'findings' key) or a raw list.
    Returns a price quote dict.
    """
    if isinstance(findings, list):
        items = findings
    else:
        items = findings.get("findings", [])

    high = sum(1 for f in items if str(f.get("severity", "")).upper() in ("HIGH", "ALTA", "CRÍTICO", "CRITICAL"))
    medium = sum(1 for f in items if str(f.get("severity", "")).upper() in ("MEDIUM", "MEDIA"))
    low = sum(1 for f in items if str(f.get("severity", "")).upper() in ("LOW", "BAJA"))
    total = high + medium + low

    line_items = []
    if high:
        line_items.append({
            "description": "Hallazgos de severidad Alta — remediación",
            "quantity": high,
            "unit_price": PRICE_HIGH,
            "subtotal": high * PRICE_HIGH,
        })
    if medium:
        line_items.append({
            "description": "Hallazgos de severidad Media — remediación",
            "quantity": medium,
            "unit_price": PRICE_MEDIUM,
            "subtotal": medium * PRICE_MEDIUM,
        })
    if low:
        line_items.append({
            "description": "Hallazgos de severidad Baja — remediación",
            "quantity": low,
            "unit_price": PRICE_LOW,
            "subtotal": low * PRICE_LOW,
        })

    subtotal = sum(li["subtotal"] for li in line_items)

    if total > DISCOUNT_TIER_2_THRESHOLD:
        discount_pct = DISCOUNT_TIER_2_PCT
    elif total > DISCOUNT_TIER_1_THRESHOLD:
        discount_pct = DISCOUNT_TIER_1_PCT
    else:
        discount_pct = 0

    discount_amount = round(subtotal * discount_pct / 100, 2)
    remediation_total = round(subtotal - discount_amount, 2)

    monthly_monitoring = MONITORING_RATES.get(tier, MONITORING_RATES["basic"])

    return {
        "counts": {"high": high, "medium": medium, "low": low, "total": total},
        "line_items": line_items,
        "subtotal": round(subtotal, 2),
        "discount_pct": discount_pct,
        "discount_amount": discount_amount,
        "remediation_total": remediation_total,
        "monthly_monitoring": monthly_monitoring,
        "currency": "EUR",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cifra audit pricing calculator")
    parser.add_argument("findings_json", help="Path to findings.json")
    parser.add_argument("--tier", default="basic",
                        choices=["basic", "pro", "premium", "enterprise"],
                        help="Client tier (affects monthly monitoring rate)")
    args = parser.parse_args()

    path = Path(args.findings_json)
    if not path.exists():
        print(f"[ERROR] File not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        findings = json.load(f)

    quote = calculate(findings, tier=args.tier)
    print(json.dumps(quote, indent=2, ensure_ascii=False))
