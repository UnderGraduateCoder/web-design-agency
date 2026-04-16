"""
security_audit.py

Usage:
    python tools/security_audit.py --target https://github.com/client/repo --client-slug acme-corp
    python tools/security_audit.py --target /path/to/local/repo --client-slug acme-corp
    python tools/security_audit.py --target . --client-slug self-audit --skip-contract

Performs a security audit on a target repository using Anthropic's Claude AI, based on
the official claude-code-security-review framework (security-review/). Requires a signed
authorization contract at brand_assets/{client_slug}/authorization_signed.pdf before
scanning any client system.

Outputs a structured findings report to:
    output/audits/{client_slug}/findings.json

Requirements:
    pip install anthropic python-dotenv
    ANTHROPIC_API_KEY must be set in .env
"""

import sys
import json
import os
import argparse
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import anthropic
except ImportError:
    print("Error: 'anthropic' package not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
SECURITY_REVIEW_DIR = PROJECT_ROOT / "security-review"

# Extensions to scan (skip binaries, media, lock files)
SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".rb",
    ".php", ".cs", ".cpp", ".c", ".h", ".sh", ".bash", ".yaml", ".yml",
    ".json", ".env.example", ".toml", ".cfg", ".ini", ".xml", ".sql",
    ".html", ".htm", ".vue", ".svelte",
}

# Directories to always skip
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    "security-review",  # skip the tool itself
}

# Max file size to read (bytes) — skip large generated files
MAX_FILE_BYTES = 50_000

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192


# ---------------------------------------------------------------------------
# Authorization gate
# ---------------------------------------------------------------------------

def verify_authorization(client_slug: str, contract_path: Path | None) -> Path:
    """Abort if no signed authorization contract is on file for this client."""
    if contract_path is None:
        contract_path = PROJECT_ROOT / "brand_assets" / client_slug / "authorization_signed.pdf"

    if not contract_path.exists():
        print(
            f"\n[ABORT] No signed authorization contract found at:\n"
            f"  {contract_path}\n\n"
            "Per agency policy, security audits CANNOT begin without a signed\n"
            "authorization_contract_template.md from the client.\n\n"
            "Steps:\n"
            "  1. Fill in templates/authorization_contract_template.md\n"
            "  2. Have the client sign and return as PDF\n"
            f"  3. Save the signed PDF to: brand_assets/{client_slug}/authorization_signed.pdf\n"
            "  4. Re-run this script.\n"
        )
        sys.exit(1)

    print(f"[OK] Authorization contract verified: {contract_path}")
    return contract_path


# ---------------------------------------------------------------------------
# Target resolution
# ---------------------------------------------------------------------------

def resolve_target(target: str, client_slug: str) -> tuple[Path, bool]:
    """Return (local_path, was_cloned). Clones remote URLs into .tmp/."""
    if target.startswith("http://") or target.startswith("https://") or target.startswith("git@"):
        tmp_dir = PROJECT_ROOT / ".tmp" / f"audit_{client_slug}"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        print(f"[INFO] Cloning {target} into {tmp_dir} ...")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", target, str(tmp_dir)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"[ERROR] git clone failed:\n{result.stderr}")
            sys.exit(1)
        print(f"[OK] Cloned into {tmp_dir}")
        return tmp_dir, True

    local = Path(target).resolve()
    if not local.exists():
        print(f"[ERROR] Target path does not exist: {local}")
        sys.exit(1)
    print(f"[INFO] Using local target: {local}")
    return local, False


# ---------------------------------------------------------------------------
# Code collection
# ---------------------------------------------------------------------------

def collect_files(root: Path) -> dict[str, str]:
    """Walk root and collect {relative_path: content} for scannable files."""
    files: dict[str, str] = {}

    for path in root.rglob("*"):
        if path.is_dir():
            continue

        # Skip unwanted dirs
        if any(part in SKIP_DIRS for part in path.parts):
            continue

        if path.suffix.lower() not in SCANNABLE_EXTENSIONS:
            continue

        if path.stat().st_size > MAX_FILE_BYTES:
            continue

        rel = str(path.relative_to(root))
        try:
            files[rel] = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass  # skip unreadable files

    return files


def build_codebase_context(files: dict[str, str], max_chars: int = 120_000) -> str:
    """Serialize collected files into a single context string, truncating at max_chars."""
    parts = []
    total = 0
    for rel_path, content in files.items():
        block = f"=== FILE: {rel_path} ===\n{content}\n"
        if total + len(block) > max_chars:
            parts.append("=== [truncated — codebase too large, showing representative sample] ===")
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Security audit prompt (adapted for local full-codebase scan)
# ---------------------------------------------------------------------------

def build_audit_prompt(target: str, codebase: str) -> str:
    """Build the security audit prompt using Anthropic's official prompt structure."""
    return f"""You are a senior security engineer performing a security audit of the following codebase.

TARGET: {target}

OBJECTIVE:
Identify HIGH-CONFIDENCE security vulnerabilities with real exploitation potential.
This is not a general code review — focus exclusively on security implications.

CRITICAL INSTRUCTIONS:
1. MINIMIZE FALSE POSITIVES: Only flag issues where you're >80% confident of actual exploitability.
2. AVOID NOISE: Skip theoretical issues, style concerns, or low-impact findings.
3. FOCUS ON IMPACT: Prioritize vulnerabilities that could lead to unauthorized access, data breaches, or system compromise.
4. DO NOT REPORT: DoS/resource exhaustion, disk-stored secrets, rate limiting, memory leaks, outdated third-party libraries.

SECURITY CATEGORIES TO EXAMINE:

**Input Validation Vulnerabilities:**
- SQL injection via unsanitized user input
- Command injection in system calls or subprocesses
- XXE injection in XML parsing
- Template injection in templating engines
- NoSQL injection in database queries
- Path traversal in file operations

**Authentication & Authorization Issues:**
- Authentication bypass logic
- Privilege escalation paths
- Session management flaws
- JWT token vulnerabilities
- Authorization logic bypasses

**Crypto & Secrets Management:**
- Hardcoded API keys, passwords, or tokens in source code
- Weak cryptographic algorithms or implementations
- Improper key storage or management
- Cryptographic randomness issues
- Certificate validation bypasses

**Injection & Code Execution:**
- Remote code execution via deserialization
- Pickle injection in Python
- YAML deserialization vulnerabilities
- Eval injection in dynamic code execution
- XSS vulnerabilities in web applications (reflected, stored, DOM-based)

**Data Exposure:**
- Sensitive data logging or storage
- PII handling violations
- API endpoint data leakage
- Debug information exposure

ANALYSIS METHODOLOGY:
Phase 1 — Context: Understand the project's purpose, tech stack, and security model.
Phase 2 — Pattern Analysis: Identify established vs. inconsistent security patterns.
Phase 3 — Vulnerability Assessment: Trace data flows, locate injection points, assess exploitability.

SEVERITY GUIDELINES:
- HIGH: Directly exploitable → RCE, data breach, authentication bypass
- MEDIUM: Significant impact requiring specific conditions
- LOW: Defense-in-depth improvements or lower-impact issues

REQUIRED OUTPUT FORMAT — respond with ONLY valid JSON, no markdown, no code blocks:

{{
  "findings": [
    {{
      "file_path": "src/auth.py",
      "line_number": 42,
      "severity": "HIGH",
      "category": "sql_injection",
      "description": "User input passed directly to SQL query without parameterization",
      "exploit_scenario": "Attacker submits SQL payload in the 'search' parameter to extract all user records",
      "recommendation": "Use parameterized queries or an ORM — never concatenate user input into SQL strings",
      "confidence": 0.95
    }}
  ],
  "analysis_summary": {{
    "files_reviewed": 12,
    "high_severity": 1,
    "medium_severity": 0,
    "low_severity": 0,
    "review_completed": true
  }}
}}

CODEBASE:
{codebase}

Begin your analysis. Your final reply must contain the JSON and nothing else.
"""


# ---------------------------------------------------------------------------
# Claude API call
# ---------------------------------------------------------------------------

def run_audit(target: str, codebase_context: str) -> dict:
    """Call Claude with the audit prompt and return parsed findings dict."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_audit_prompt(target, codebase_context)

    print(f"[INFO] Sending {len(prompt):,} chars to Claude ({CLAUDE_MODEL}) ...")

    for attempt in range(1, 4):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            # Strip accidental markdown fences
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.rsplit("```", 1)[0].strip()

            return json.loads(text)

        except json.JSONDecodeError as e:
            print(f"[WARN] Attempt {attempt}: JSON parse error — {e}")
            if attempt == 3:
                print("[ERROR] Could not parse Claude response as JSON after 3 attempts.")
                sys.exit(1)
        except Exception as e:
            print(f"[WARN] Attempt {attempt}: API error — {e}")
            if attempt == 3:
                print("[ERROR] API call failed after 3 attempts.")
                sys.exit(1)

    return {}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_findings(client_slug: str, target: str, contract_path: Path, results: dict) -> Path:
    """Write findings.json and print a summary."""
    out_dir = PROJECT_ROOT / "output" / "audits" / client_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "findings.json"

    findings = results.get("findings", [])
    summary = results.get("analysis_summary", {})

    output = {
        "client_slug": client_slug,
        "target": target,
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "contract_path": str(contract_path),
        "summary": {
            "total": len(findings),
            "high": sum(1 for f in findings if f.get("severity") == "HIGH"),
            "medium": sum(1 for f in findings if f.get("severity") == "MEDIUM"),
            "low": sum(1 for f in findings if f.get("severity") == "LOW"),
            "files_reviewed": summary.get("files_reviewed", 0),
        },
        "findings": findings,
    }

    out_file.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"AUDIT COMPLETE — {client_slug}")
    print(f"{'='*60}")
    print(f"  Files reviewed : {output['summary']['files_reviewed']}")
    print(f"  HIGH           : {output['summary']['high']}")
    print(f"  MEDIUM         : {output['summary']['medium']}")
    print(f"  LOW            : {output['summary']['low']}")
    print(f"  Report saved   : {out_file}")
    print(f"{'='*60}\n")

    return out_file


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="WAT Security Audit Tool")
    parser.add_argument(
        "--target", required=True,
        help="GitHub URL or local path of the repository to audit"
    )
    parser.add_argument(
        "--client-slug", required=True,
        help="Client identifier used for output paths (e.g. acme-corp)"
    )
    parser.add_argument(
        "--contract-path",
        help="Override default contract path (brand_assets/{client_slug}/authorization_signed.pdf)"
    )
    parser.add_argument(
        "--skip-contract", action="store_true",
        help="Skip authorization check — ONLY for self-audits of this project"
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"WAT SECURITY AUDIT — {args.client_slug}")
    print(f"{'='*60}\n")

    # 1. Authorization gate
    if args.skip_contract:
        print("[WARN] --skip-contract flag set. Skipping authorization check (self-audit only).")
        contract_path = Path("N/A — self-audit")
    else:
        contract_path = args.contract_path and Path(args.contract_path)
        contract_path = verify_authorization(args.client_slug, contract_path)

    # 2. Resolve target
    local_path, was_cloned = resolve_target(args.target, args.client_slug)

    # 3. Collect files
    print(f"[INFO] Collecting scannable files from {local_path} ...")
    files = collect_files(local_path)
    print(f"[INFO] Found {len(files)} scannable files.")

    if not files:
        print("[ERROR] No scannable files found. Check the target path.")
        sys.exit(1)

    codebase_context = build_codebase_context(files)

    # 4. Run audit
    results = run_audit(args.target, codebase_context)

    # 5. Write output
    out_file = write_findings(args.client_slug, args.target, contract_path, results)

    # 6. Cleanup cloned repo
    if was_cloned:
        shutil.rmtree(local_path, ignore_errors=True)
        print(f"[INFO] Cleaned up temporary clone.")

    print(f"[DONE] Next step: render report using templates/audit_report_template.md")
    print(f"       Findings: {out_file}\n")


if __name__ == "__main__":
    main()
