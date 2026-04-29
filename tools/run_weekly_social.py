"""Weekly social content runner — designed for Windows Task Scheduler.

Schedule: weekly, e.g. every Monday at 09:00 (after run_weekly_blog.py)
Task Scheduler command: python tools/run_weekly_social.py
Working directory: <project root>
Exit code 0 = all OK, 1 = one or more clients failed
"""
import sys
import subprocess
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
import db


def _get_social_clients() -> list[str]:
    """Return slugs of all clients with an active social_content_pack subscription."""
    with db._connect() as conn:
        rows = conn.execute(
            """SELECT clients.slug
               FROM clients
               JOIN client_services ON clients.id = client_services.client_id
               WHERE client_services.service_code = 'social_content_pack'
                 AND client_services.active = 1
               ORDER BY clients.slug""",
        ).fetchall()
    return [r["slug"] for r in rows]


def main():
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[run_weekly_social] Started at {started}")

    slugs = _get_social_clients()
    if not slugs:
        print("[run_weekly_social] No active social_content_pack subscribers — nothing to do.")
        sys.exit(0)

    print(f"[run_weekly_social] Processing {len(slugs)} client(s): {', '.join(slugs)}")

    failures = []
    for slug in slugs:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] Generating social pack for: {slug}")
        result = subprocess.run(
            [sys.executable, "tools/generate_social_posts.py", "--client-slug", slug],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  [OK] {slug}")
            if result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    print(f"       {line}")
        else:
            print(f"  [FAIL] {slug}")
            print(f"       STDOUT: {result.stdout.strip()}")
            print(f"       STDERR: {result.stderr.strip()}")
            failures.append(slug)

    finished = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok_count = len(slugs) - len(failures)
    print(f"\n[run_weekly_social] Finished at {finished} — {ok_count}/{len(slugs)} OK")

    if failures:
        print(f"[run_weekly_social] FAILED: {', '.join(failures)}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
