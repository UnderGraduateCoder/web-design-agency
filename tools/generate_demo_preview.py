"""
generate_demo_preview.py

Usage:
    python tools/generate_demo_preview.py --lead-id 42

Pulls public info for a lead, runs the full website builder pipeline
(gather_business_info → generate_copy → build_website), and outputs a
fully-branded demo to output/demos/{business_slug}/index.html.

Updates lead status to 'demo_sent' on success.

Note: After running this script, Claude should call
mcp__21st-magic__logo_search to enrich logo treatment in the generated site.
"""

import sys
import io
import os
import re
import json
import subprocess
import argparse
import shutil
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.db import get_lead, update_lead_status


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _run(cmd: list, label: str) -> subprocess.CompletedProcess:
    print(f"\n  [{label}] Running: {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"  [ERROR] {label} exited with code {result.returncode}")
        sys.exit(result.returncode)
    return result


def run(lead_id: int) -> Path:
    lead = get_lead(lead_id)
    if not lead:
        print(f"[ERROR] Lead {lead_id} not found.")
        sys.exit(1)

    name = lead["business_name"]
    sector = lead.get("sector", "")
    region = lead.get("region", "")
    slug = _slug(name)

    print(f"\n[Demo Generator] Lead #{lead_id}: {name}")
    print(f"  Sector : {sector}")
    print(f"  Region : {region}")
    print(f"  Slug   : {slug}")

    output_dir = Path(f"output/demos/{slug}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1 — Gather business info
    description = f"{name}, {sector}, {region}".strip(", ")
    _run(
        [sys.executable, "tools/gather_business_info.py", description],
        "gather_business_info",
    )

    # Step 2 — Generate copy
    _run([sys.executable, "tools/generate_copy.py"], "generate_copy")

    # Step 3 — Build website (output to demo folder)
    build_tool = Path("tools/build_website.py")
    _run(
        [sys.executable, str(build_tool), "--output-dir", str(output_dir)],
        "build_website",
    )

    # Verify output exists; fallback: copy from default output
    demo_html = output_dir / "index.html"
    if not demo_html.exists():
        fallback = Path("output/index.html")
        if fallback.exists():
            shutil.copy(fallback, demo_html)
            print(f"  [INFO] Copied fallback output to {demo_html}")
        else:
            print(f"  [ERROR] build_website did not produce index.html")
            sys.exit(1)

    # Step 4 — Update lead status
    update_lead_status(lead_id, "demo_sent")

    print(f"\n[OK] Demo generated: {demo_html}")
    print(f"     Lead status → demo_sent")
    print(f"\nNext: call mcp__21st-magic__logo_search for '{name}' to enrich logo treatment.")

    return demo_html


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate personalized demo for a lead")
    parser.add_argument("--lead-id", type=int, required=True)
    args = parser.parse_args()
    run(args.lead_id)
