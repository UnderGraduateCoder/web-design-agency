"""
run_monthly_audits.py

Usage:
    python tools/run_monthly_audits.py [--dry-run]

Designed to run weekly via Windows Task Scheduler. For every client with an
active security retainer service, runs the appropriate scan, compares findings
to the previous scan (diff: new / resolved / persistent), generates a PDF
report, and logs a billing line item.

Schedule (Windows Task Scheduler):
    Action: python "C:\\path\\to\\tools\\run_monthly_audits.py"
    Trigger: Weekly (Sunday, 02:00)

All log output goes to data/audit_scheduler.log — never to stdout.
"""

import sys
import json
import logging
import argparse
import subprocess
import importlib.util
from datetime import date, datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).parent.parent
LOG_FILE = PROJECT_ROOT / "data" / "audit_scheduler.log"

# ---------------------------------------------------------------------------
# Logging — file only, never stdout
# ---------------------------------------------------------------------------

def _setup_logging(dry_run: bool) -> logging.Logger:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("monthly_audits")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    if dry_run:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(logging.Formatter("[DRY-RUN] %(message)s"))
        logger.addHandler(sh)

    return logger


# ---------------------------------------------------------------------------
# DB helpers (inline to avoid import issues when run from scheduler)
# ---------------------------------------------------------------------------

def _load_db_module():
    spec = importlib.util.spec_from_file_location(
        "db", str(PROJECT_ROOT / "tools" / "db.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------

def _fingerprint(finding: dict) -> str:
    """Stable identifier for a finding across scans."""
    return "|".join([
        finding.get("category", ""),
        finding.get("file_path", ""),
        str(finding.get("line_number", "")),
    ])


def compute_diff(previous: list[dict], current: list[dict]) -> dict:
    """Return new / resolved / persistent finding sets."""
    prev_fp = {_fingerprint(f): f for f in previous}
    curr_fp = {_fingerprint(f): f for f in current}

    new_findings        = [f for fp, f in curr_fp.items() if fp not in prev_fp]
    resolved_findings   = [f for fp, f in prev_fp.items() if fp not in curr_fp]
    persistent_findings = [f for fp, f in curr_fp.items() if fp in prev_fp]

    return {
        "new":        new_findings,
        "resolved":   resolved_findings,
        "persistent": persistent_findings,
    }


# ---------------------------------------------------------------------------
# Per-client audit runner
# ---------------------------------------------------------------------------

def _run_client_audit(
    client: dict,
    db,
    logger: logging.Logger,
    dry_run: bool,
) -> bool:
    slug = client["slug"]
    tier = client.get("tier", "basic")
    target = client.get("website_output_path") or str(PROJECT_ROOT / "output" / "index.html")

    # Determine scan mode: public URL scan for Pro+, repo for basic
    scan_mode = "public_url" if tier in ("pro", "premium", "enterprise") and target.startswith("http") \
                else "pre_launch" if target.endswith(".html") \
                else "repo"

    logger.info(f"Starting audit for {slug} (tier={tier}, mode={scan_mode})")

    if dry_run:
        logger.info(f"[DRY-RUN] Would scan {target} with mode={scan_mode}")
        return True

    # Run the audit
    audit_script = PROJECT_ROOT / "tools" / "security_audit.py"
    result = subprocess.run(
        [sys.executable, str(audit_script),
         "--target", target,
         "--client-slug", slug,
         "--scan-mode", scan_mode,
         "--skip-contract"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        logger.error(f"Audit failed for {slug}: {result.stderr[:500]}")
        return False

    findings_path = PROJECT_ROOT / "output" / "audits" / slug / "findings.json"
    if not findings_path.exists():
        logger.error(f"findings.json not found after audit for {slug}")
        return False

    with open(findings_path, encoding="utf-8") as fh:
        current_data = json.load(fh)
    current_findings = current_data.get("findings", [])
    summary = current_data.get("summary", {})

    # Load previous findings for diff
    prev_findings: list[dict] = []
    prev_audits = None
    try:
        with db._connect() as conn:
            prev_audits = conn.execute(
                """SELECT findings_json_path FROM audits
                   WHERE client_id = (SELECT id FROM clients WHERE slug = ?)
                   ORDER BY scan_date DESC LIMIT 1""",
                (slug,),
            ).fetchone()
    except Exception as e:
        logger.warning(f"Could not query previous audit for {slug}: {e}")

    if prev_audits and prev_audits["findings_json_path"]:
        prev_path = Path(prev_audits["findings_json_path"])
        if prev_path.exists():
            try:
                with open(prev_path, encoding="utf-8") as fh:
                    prev_data = json.load(fh)
                prev_findings = prev_data.get("findings", [])
            except Exception:
                pass

    diff = compute_diff(prev_findings, current_findings)

    # Save diff report
    diff_path = findings_path.parent / f"diff_{date.today().isoformat()}.json"
    diff_report = {
        "client_slug": slug,
        "scan_date": datetime.utcnow().isoformat(),
        "scan_mode": scan_mode,
        "summary": {
            "new":        len(diff["new"]),
            "resolved":   len(diff["resolved"]),
            "persistent": len(diff["persistent"]),
        },
        "new":        diff["new"],
        "resolved":   diff["resolved"],
        "persistent": diff["persistent"],
    }
    diff_path.write_text(json.dumps(diff_report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(
        f"{slug}: {len(diff['new'])} new / {len(diff['resolved'])} resolved / "
        f"{len(diff['persistent'])} persistent findings"
    )

    # Generate PDF report from diff (write a synthetic findings.json for the report)
    monthly_findings_path = findings_path.parent / f"monthly_{date.today().strftime('%Y-%m')}_findings.json"
    monthly_data = dict(current_data)
    monthly_data["findings"] = current_findings
    monthly_data["diff"] = diff_report["summary"]
    monthly_findings_path.write_text(
        json.dumps(monthly_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    pdf_script = PROJECT_ROOT / "tools" / "generate_audit_pdf.py"
    pdf_result = subprocess.run(
        [sys.executable, str(pdf_script), str(monthly_findings_path), slug],
        capture_output=True, text=True,
    )
    if pdf_result.returncode != 0:
        logger.warning(f"PDF generation failed for {slug}: {pdf_result.stderr[:300]}")
        pdf_path = None
    else:
        pdf_path = pdf_result.stdout.strip()
        logger.info(f"PDF report saved: {pdf_path}")

    # Log audit to DB
    try:
        db.add_audit(
            client_slug=slug,
            scan_type="public_url" if scan_mode == "public_url" else "website_build" if scan_mode == "pre_launch" else "repo",
            findings_json_path=str(findings_path),
            report_pdf_path=pdf_path,
            total_findings=summary.get("total", 0),
            high=summary.get("high", 0),
            medium=summary.get("medium", 0),
            low=summary.get("low", 0),
        )
    except Exception as e:
        logger.warning(f"Could not log audit to DB for {slug}: {e}")

    # Log billing line item
    today = date.today()
    period_start = today.replace(day=1).isoformat()
    next_month = (today.replace(day=28) + __import__("datetime").timedelta(days=4))
    period_end = next_month.replace(day=1).isoformat()

    security_fee = client.get("monthly_security_fee") or 79.0
    line_items = [
        {
            "description": f"Auditoría de seguridad mensual — {scan_mode}",
            "quantity": 1,
            "unit_price": security_fee,
            "subtotal": security_fee,
        },
        {
            "description": f"Hallazgos nuevos detectados: {len(diff['new'])}",
            "quantity": 1,
            "unit_price": 0,
            "subtotal": 0,
        },
    ]

    try:
        db.log_billing(
            client_slug=slug,
            period_start=period_start,
            period_end=period_end,
            line_items=line_items,
            total=security_fee,
            paid=False,
            invoice_path=pdf_path,
        )
        logger.info(f"{slug}: billing logged — €{security_fee:.0f} for {period_start}→{period_end}")
    except Exception as e:
        logger.warning(f"Could not log billing for {slug}: {e}")

    # Competitor monitoring for pro+ clients
    if tier in ("pro", "premium", "enterprise"):
        try:
            monitor_script = PROJECT_ROOT / "tools" / "monitor_competitors.py"
            mon_result = subprocess.run(
                [sys.executable, str(monitor_script),
                 "--client-slug", slug,
                 *(["--dry-run"] if dry_run else [])],
                capture_output=True, text=True, check=False,
            )
            if mon_result.returncode == 0:
                logger.info(f"{slug}: competitor scan complete")
            else:
                logger.warning(f"{slug}: competitor scan failed — {mon_result.stderr.strip()[:200]}")
        except Exception as e:
            logger.warning(f"{slug}: competitor monitoring error — {e}")

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Cifra monthly security audit scheduler")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be done without actually running audits")
    args = parser.parse_args()

    logger = _setup_logging(args.dry_run)
    logger.info("=" * 60)
    logger.info(f"Monthly audit run started — {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Load DB module
    try:
        db = _load_db_module()
        db.init_db()
    except Exception as e:
        logger.error(f"Could not initialize DB: {e}")
        sys.exit(1)

    # Find all clients with an active security retainer
    try:
        with db._connect() as conn:
            retainer_clients = conn.execute(
                """SELECT DISTINCT c.* FROM clients c
                   JOIN client_services cs ON cs.client_id = c.id
                   JOIN services_catalog sc ON sc.service_code = cs.service_code
                   WHERE cs.active = 1
                     AND sc.service_code LIKE 'seg_retainer%'""",
            ).fetchall()
    except Exception as e:
        logger.error(f"Could not query clients: {e}")
        sys.exit(1)

    clients = [dict(r) for r in retainer_clients]
    logger.info(f"Found {len(clients)} clients with active security retainers.")

    if not clients:
        logger.info("No clients to scan. Exiting.")
        return

    success = 0
    failed = 0
    for client in clients:
        try:
            ok = _run_client_audit(client, db, logger, dry_run=args.dry_run)
            if ok:
                success += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Unhandled error for {client.get('slug', '?')}: {e}")
            failed += 1

    logger.info(f"Run complete — {success} succeeded, {failed} failed.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
