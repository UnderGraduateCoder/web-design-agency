"""
orchestrate_build.py

Multi-pass website build orchestrator. Runs the full pipeline with
hero-first gate review and tier-gated animation polish.

Usage:
    python tools/orchestrate_build.py --tier starter --input "Panadería Lola, Barcelona..."
    python tools/orchestrate_build.py --tier pro --input "..." --brief .tmp/design_brief.json
    python tools/orchestrate_build.py --tier enterprise --input "..." --place-id ChIJ...

Tier pass count:
    starter / basic : 2 passes  (hero → full site)
    pro             : 3 passes  (hero → full site → animation polish)
    enterprise      : 4 passes  (hero → full site → animation polish → [future: integrations])
"""

import sys
import subprocess
import argparse
from pathlib import Path


TIER_PASS_COUNT = {
    "starter":    2,
    "basic":      2,
    "pro":        3,
    "enterprise": 4,
}


def run(cmd: list[str]) -> None:
    print(f"\n{'='*60}")
    print(f"[RUN] {' '.join(cmd)}")
    print('='*60)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n[ERROR] Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def gate(message: str, auto: bool = False) -> None:
    """Pause for human review unless --auto flag is set."""
    print(f"\n{'─'*60}")
    print(f"[GATE] {message}")
    if auto:
        print("       (--auto mode: skipping review gate)")
        return
    print("       Press Enter to continue, or Ctrl+C to abort...")
    try:
        input()
    except KeyboardInterrupt:
        print("\n[ABORTED] Build stopped at gate.")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Multi-pass website build orchestrator")
    parser.add_argument("--input", required=True, help="Plain-text business description")
    parser.add_argument(
        "--tier", default="starter",
        choices=["starter", "basic", "pro", "enterprise"],
        help="Client tier - controls pass count and animation depth",
    )
    parser.add_argument("--brief", default=None, help="Path to design_brief.json (Client Mode)")
    parser.add_argument("--place-id", default=None, help="Google Places ID for real reviews")
    parser.add_argument(
        "--auto", action="store_true",
        help="Skip interactive gate prompts (for CI / non-interactive runs)",
    )
    args = parser.parse_args()

    passes = TIER_PASS_COUNT.get(args.tier, 2)
    print(f"\n[ORCHESTRATOR] Tier: {args.tier} → {passes} passes")

    # -------------------------------------------------------------------------
    # Step 1: gather business info
    # -------------------------------------------------------------------------
    gather_cmd = ["python", "tools/gather_business_info.py", args.input]
    if args.place_id:
        gather_cmd += ["--place-id", args.place_id]
    run(gather_cmd)

    # -------------------------------------------------------------------------
    # Pass 1: hero copy + hero preview
    # -------------------------------------------------------------------------
    run(["python", "tools/generate_copy.py", "--pass", "1"])

    preview_cmd = ["python", "tools/build_website.py", "--preview"]
    if args.brief:
        preview_cmd += ["--brief", args.brief]
    run(preview_cmd)

    gate(
        "Hero preview saved to output/hero_preview.html\n"
        "       Open it in a browser, review the hero section.\n"
        "       If unsatisfactory, Ctrl+C and re-run: python tools/generate_copy.py --pass 1",
        auto=args.auto,
    )

    # -------------------------------------------------------------------------
    # Pass 2: remaining sections + full site build
    # -------------------------------------------------------------------------
    run(["python", "tools/generate_copy.py", "--pass", "2"])

    build_cmd = ["python", "tools/build_website.py"]
    if args.brief:
        build_cmd += ["--brief", args.brief]
    run(build_cmd)

    if passes < 3:
        print(f"\n[DONE] Build complete (2 passes) → output/index.html")
        return

    gate(
        "Full site saved to output/index.html\n"
        "       Review the complete site before animation polish pass.",
        auto=args.auto,
    )

    # -------------------------------------------------------------------------
    # Pass 3: animation polish (pro / enterprise)
    # -------------------------------------------------------------------------
    run(["python", "tools/build_website.py", "--polish", "--tier", args.tier])
    print(f"\n[DONE] Build complete (3 passes, {args.tier} animations) → output/index.html")

    if passes < 4:
        return

    # -------------------------------------------------------------------------
    # Pass 4: enterprise custom integrations (placeholder — extend as needed)
    # -------------------------------------------------------------------------
    print("\n[PASS 4] Enterprise integrations pass (extend orchestrate_build.py as needed)")
    print(f"\n[DONE] Build complete (4 passes) → output/index.html")


if __name__ == "__main__":
    main()
