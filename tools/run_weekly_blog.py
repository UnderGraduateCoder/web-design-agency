"""Weekly blog post runner — designed for Windows Task Scheduler.

Schedule: weekly, e.g. every Monday at 08:00
Task Scheduler command: python tools/run_weekly_blog.py
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


def _get_blog_clients() -> list[str]:
    """Return slugs of all clients with an active blog_mensual subscription."""
    with db._connect() as conn:
        rows = conn.execute(
            """SELECT clients.slug
               FROM clients
               JOIN client_services ON clients.id = client_services.client_id
               WHERE client_services.service_code = 'blog_mensual'
                 AND client_services.active = 1
               ORDER BY clients.slug""",
        ).fetchall()
    return [r["slug"] for r in rows]


def main():
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[run_weekly_blog] Started at {started}")

    slugs = _get_blog_clients()
    if not slugs:
        print("[run_weekly_blog] No active blog_mensual subscribers — nothing to do.")
        sys.exit(0)

    print(f"[run_weekly_blog] Processing {len(slugs)} client(s): {', '.join(slugs)}")

    failures = []
    for slug in slugs:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] Generating blog post for: {slug}")
        result = subprocess.run(
            [sys.executable, "tools/generate_blog_post.py", "--client-slug", slug],
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
    print(f"\n[run_weekly_blog] Finished at {finished} — {ok_count}/{len(slugs)} OK")

    if failures:
        print(f"[run_weekly_blog] FAILED: {', '.join(failures)}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
