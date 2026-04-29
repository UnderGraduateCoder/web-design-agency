"""
security_audit.py

Usage:
    # Repo scan (default)
    python tools/security_audit.py --target https://github.com/client/repo --client-slug acme-corp
    python tools/security_audit.py --target /path/to/local/repo --client-slug acme-corp

    # Public URL passive scan
    python tools/security_audit.py --target https://example.com --client-slug acme-corp --scan-mode public_url

    # Pre-launch bundle scan (own output, no contract needed)
    python tools/security_audit.py --target output/index.html --client-slug acme-corp --scan-mode pre_launch --skip-contract

    # Self-audit
    python tools/security_audit.py --target . --client-slug self-audit --skip-contract

Outputs findings to: output/audits/{client_slug}/findings.json

SECURITY: Requires a signed authorization contract at
    brand_assets/{client_slug}/authorization_signed.pdf
before scanning any client system (all modes, except --skip-contract).
No active exploitation — passive observation only.
"""

import sys
import json
import os
import re
import ssl
import socket
import argparse
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import requests
    from requests.exceptions import RequestException
except ImportError:
    requests = None

try:
    import anthropic
except ImportError:
    print("Error: 'anthropic' package not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
    _BS4 = True
except ImportError:
    _BS4 = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
SECURITY_REVIEW_DIR = PROJECT_ROOT / "security-review"

SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".rb",
    ".php", ".cs", ".cpp", ".c", ".h", ".sh", ".bash", ".yaml", ".yml",
    ".json", ".env.example", ".toml", ".cfg", ".ini", ".xml", ".sql",
    ".html", ".htm", ".vue", ".svelte",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    "security-review",
}

MAX_FILE_BYTES = 50_000
CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192

# Security headers that should be present on every production site
REQUIRED_HEADERS = {
    "Content-Security-Policy":      ("A05:2021", ["A.14.1.2"], ["Art. 32"]),
    "Strict-Transport-Security":    ("A02:2021", ["A.14.1.2", "A.10.1.1"], ["Art. 32"]),
    "X-Frame-Options":              ("A05:2021", ["A.14.2.5"], ["Art. 32"]),
    "X-Content-Type-Options":       ("A05:2021", ["A.14.2.5"], []),
    "Referrer-Policy":              ("A05:2021", ["A.13.2.1"], ["Art. 13"]),
    "Permissions-Policy":           ("A05:2021", ["A.14.1.2"], []),
}

# Paths commonly exposed by misconfigured servers
EXPOSED_PATH_PROBES = [
    "/.env",
    "/.git/config",
    "/.git/HEAD",
    "/admin",
    "/wp-admin",
    "/wp-login.php",
    "/debug",
    "/phpinfo.php",
    "/.htaccess",
    "/server-status",
    "/actuator",
    "/actuator/env",
    "/console",
    "/.DS_Store",
    "/config.php",
    "/config.yml",
    "/config.yaml",
]

# Patterns that suggest hardcoded secrets in HTML/JS source
SECRET_PATTERNS = [
    (r'api[_-]?key\s*[=:]\s*["\']([A-Za-z0-9_\-]{20,})["\']', "Hardcoded API key"),
    (r'secret[_-]?key\s*[=:]\s*["\']([A-Za-z0-9_\-]{20,})["\']', "Hardcoded secret key"),
    (r'password\s*[=:]\s*["\']([^"\']{6,})["\']', "Hardcoded password"),
    (r'token\s*[=:]\s*["\']([A-Za-z0-9_\-\.]{20,})["\']', "Hardcoded token"),
    (r'AKIA[0-9A-Z]{16}', "AWS Access Key ID"),
    (r'sk-[A-Za-z0-9]{32,}', "OpenAI API key pattern"),
    (r'ghp_[A-Za-z0-9]{36}', "GitHub Personal Access Token"),
]

# ---------------------------------------------------------------------------
# Compliance mapping: finding category → OWASP / ISO 27001 / RGPD
# ---------------------------------------------------------------------------

COMPLIANCE_MAP: dict[str, dict] = {
    # Header findings
    "missing_csp":                  {"owasp": ["A05:2021"], "iso27001": ["A.14.1.2", "A.14.2.5"], "rgpd": ["Art. 32"]},
    "missing_hsts":                 {"owasp": ["A02:2021"], "iso27001": ["A.14.1.2", "A.10.1.1"], "rgpd": ["Art. 32"]},
    "missing_x_frame_options":      {"owasp": ["A05:2021"], "iso27001": ["A.14.2.5"],              "rgpd": []},
    "missing_x_content_type":       {"owasp": ["A05:2021"], "iso27001": ["A.14.2.5"],              "rgpd": []},
    "missing_referrer_policy":      {"owasp": ["A05:2021"], "iso27001": ["A.13.2.1"],              "rgpd": ["Art. 13", "Art. 32"]},
    "missing_permissions_policy":   {"owasp": ["A05:2021"], "iso27001": ["A.14.1.2"],              "rgpd": []},
    # TLS
    "weak_tls_version":             {"owasp": ["A02:2021"], "iso27001": ["A.10.1.1"],              "rgpd": ["Art. 32"]},
    "expired_certificate":          {"owasp": ["A02:2021"], "iso27001": ["A.10.1.1"],              "rgpd": ["Art. 32"]},
    "self_signed_certificate":      {"owasp": ["A02:2021"], "iso27001": ["A.10.1.1"],              "rgpd": ["Art. 32"]},
    # Cookie flags
    "cookie_missing_httponly":      {"owasp": ["A07:2021"], "iso27001": ["A.9.4.2"],               "rgpd": ["Art. 32"]},
    "cookie_missing_secure":        {"owasp": ["A02:2021"], "iso27001": ["A.10.1.1"],              "rgpd": ["Art. 32"]},
    "cookie_missing_samesite":      {"owasp": ["A01:2021"], "iso27001": ["A.9.4.2"],               "rgpd": ["Art. 32"]},
    # Exposed resources
    "exposed_env_file":             {"owasp": ["A02:2021"], "iso27001": ["A.9.4.1", "A.13.2.1"],  "rgpd": ["Art. 32", "Art. 33"]},
    "exposed_git_config":           {"owasp": ["A05:2021"], "iso27001": ["A.9.4.1"],               "rgpd": []},
    "exposed_admin_panel":          {"owasp": ["A01:2021"], "iso27001": ["A.9.4.1"],               "rgpd": []},
    "exposed_debug_endpoint":       {"owasp": ["A05:2021"], "iso27001": ["A.14.2.7"],              "rgpd": []},
    # CSRF
    "missing_csrf_protection":      {"owasp": ["A01:2021"], "iso27001": ["A.14.1.2"],              "rgpd": ["Art. 32"]},
    # Injection / code quality
    "eval_injection":               {"owasp": ["A03:2021"], "iso27001": ["A.14.2.5"],              "rgpd": ["Art. 32"]},
    "innerHTML_assignment":         {"owasp": ["A03:2021"], "iso27001": ["A.14.2.5"],              "rgpd": []},
    "hardcoded_secret":             {"owasp": ["A02:2021"], "iso27001": ["A.9.4.3"],               "rgpd": ["Art. 32"]},
    # Mixed content
    "http_resource_on_https_page":  {"owasp": ["A02:2021"], "iso27001": ["A.10.1.1"],              "rgpd": ["Art. 32"]},
    "form_non_https_action":        {"owasp": ["A02:2021"], "iso27001": ["A.14.1.2"],              "rgpd": ["Art. 32"]},
    # Generic fallback
    "sql_injection":                {"owasp": ["A03:2021"], "iso27001": ["A.14.2.5"],              "rgpd": ["Art. 32", "Art. 33"]},
    "command_injection":            {"owasp": ["A03:2021"], "iso27001": ["A.14.2.5"],              "rgpd": ["Art. 32"]},
    "path_traversal":               {"owasp": ["A01:2021"], "iso27001": ["A.9.4.1"],               "rgpd": ["Art. 32"]},
    "xss":                          {"owasp": ["A03:2021"], "iso27001": ["A.14.2.5"],              "rgpd": []},
    "insecure_deserialization":     {"owasp": ["A08:2021"], "iso27001": ["A.14.2.5"],              "rgpd": []},
    "authentication_bypass":        {"owasp": ["A07:2021"], "iso27001": ["A.9.4.2"],               "rgpd": ["Art. 32"]},
    "sensitive_data_exposure":      {"owasp": ["A02:2021"], "iso27001": ["A.8.2.1"],               "rgpd": ["Art. 32", "Art. 33"]},
}

_CATEGORY_ALIASES = {
    # Normalize common Claude-returned category names
    "sql injection":         "sql_injection",
    "xss vulnerability":     "xss",
    "command injection":     "command_injection",
    "path traversal":        "path_traversal",
    "hardcoded secret":      "hardcoded_secret",
    "hardcoded api key":     "hardcoded_secret",
    "authentication bypass": "authentication_bypass",
}


def _lookup_compliance(category: str) -> dict:
    """Return compliance mapping for a finding category (case-insensitive, fuzzy)."""
    key = category.lower().strip().replace(" ", "_").replace("-", "_")
    if key in COMPLIANCE_MAP:
        return COMPLIANCE_MAP[key]
    # Try alias table
    alias = _CATEGORY_ALIASES.get(category.lower().strip())
    if alias and alias in COMPLIANCE_MAP:
        return COMPLIANCE_MAP[alias]
    # Partial match
    for map_key in COMPLIANCE_MAP:
        if map_key in key or key in map_key:
            return COMPLIANCE_MAP[map_key]
    return {"owasp": [], "iso27001": [], "rgpd": []}


def enrich_compliance(findings: list[dict]) -> list[dict]:
    """Add 'compliance' key to each finding dict."""
    for f in findings:
        if "compliance" not in f:
            f["compliance"] = _lookup_compliance(f.get("category", ""))
    return findings


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
    """Return (local_path, was_cloned). Clones remote git URLs into .tmp/."""
    if target.startswith("git@") or (
        (target.startswith("http://") or target.startswith("https://"))
        and (".git" in target or "github.com" in target or "gitlab.com" in target or "bitbucket.org" in target)
    ):
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
    scan_root = root if root.is_dir() else root.parent
    targets = [root] if root.is_file() else list(scan_root.rglob("*"))

    for path in targets:
        if isinstance(path, Path) and path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in SCANNABLE_EXTENSIONS:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        rel = str(path.relative_to(scan_root))
        try:
            files[rel] = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
    return files


def build_codebase_context(files: dict[str, str], max_chars: int = 120_000) -> str:
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
# Audit prompt (repo mode)
# ---------------------------------------------------------------------------

def build_audit_prompt(target: str, codebase: str) -> str:
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
# PUBLIC URL scan mode
# ---------------------------------------------------------------------------

def _check_tls(hostname: str) -> list[dict]:
    """Direct TLS inspection via ssl stdlib. Returns list of findings."""
    findings = []
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.create_connection((hostname, 443), timeout=10),
                             server_hostname=hostname) as sock:
            cert = sock.getpeercert()
            proto = sock.version()
            # Check for old TLS versions
            if proto in ("TLSv1", "TLSv1.1", "SSLv2", "SSLv3"):
                findings.append({
                    "file_path": hostname,
                    "line_number": None,
                    "severity": "HIGH",
                    "category": "weak_tls_version",
                    "description": f"Server uses deprecated TLS version: {proto}",
                    "exploit_scenario": "An attacker performing a MITM can downgrade and decrypt traffic.",
                    "recommendation": "Configure the server to require TLS 1.2 minimum (TLS 1.3 preferred).",
                    "confidence": 0.95,
                })
            # Check certificate expiry
            not_after = cert.get("notAfter", "")
            if not_after:
                from datetime import datetime
                exp = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                if exp < datetime.utcnow():
                    findings.append({
                        "file_path": hostname,
                        "line_number": None,
                        "severity": "HIGH",
                        "category": "expired_certificate",
                        "description": f"TLS certificate expired on {not_after}",
                        "exploit_scenario": "Expired certificates cause browser warnings and MITM risk.",
                        "recommendation": "Renew the TLS certificate immediately.",
                        "confidence": 1.0,
                    })
    except ssl.SSLCertVerificationError:
        findings.append({
            "file_path": hostname,
            "line_number": None,
            "severity": "MEDIUM",
            "category": "self_signed_certificate",
            "description": "TLS certificate could not be verified (possibly self-signed or untrusted CA)",
            "exploit_scenario": "Users will see browser security warnings; susceptible to MITM.",
            "recommendation": "Use a certificate from a trusted CA (e.g. Let's Encrypt).",
            "confidence": 0.80,
        })
    except Exception:
        pass
    return findings


def scan_public_url(url: str, client_slug: str) -> dict:
    """
    Passive security scan of a live URL.
    Checks: headers, TLS, exposed paths, cookie flags, CSRF protection.
    No active exploitation — observation only.
    """
    if not requests:
        print("[ERROR] 'requests' package is required for public_url scan. Run: pip install requests")
        sys.exit(1)

    print(f"[INFO] Starting passive public URL scan: {url}")
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    is_https = parsed.scheme == "https"
    findings: list[dict] = []

    # --- HTTP headers check ---
    try:
        resp = requests.get(url, timeout=15, allow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0 (security-audit/1.0)"})
        headers = {k.lower(): v for k, v in resp.headers.items()}

        for header, (owasp, iso, rgpd) in REQUIRED_HEADERS.items():
            if header.lower() not in headers:
                category = f"missing_{header.lower().replace('-', '_')}"
                findings.append({
                    "file_path": url,
                    "line_number": None,
                    "severity": "MEDIUM",
                    "category": category,
                    "description": f"Cabecera de seguridad ausente: {header}",
                    "exploit_scenario": f"Sin {header}, el navegador no aplica la política de seguridad correspondiente.",
                    "recommendation": f"Añadir la cabecera HTTP '{header}' en la configuración del servidor.",
                    "confidence": 0.95,
                })

        # --- Cookie flags ---
        for cookie in resp.cookies:
            name = cookie.name
            if not cookie.has_nonstandard_attr("HttpOnly") and not getattr(cookie, "_rest", {}).get("HttpOnly"):
                findings.append({
                    "file_path": url,
                    "line_number": None,
                    "severity": "MEDIUM",
                    "category": "cookie_missing_httponly",
                    "description": f"Cookie '{name}' sin atributo HttpOnly",
                    "exploit_scenario": "JavaScript puede leer esta cookie, facilitando ataques XSS de robo de sesión.",
                    "recommendation": f"Añadir el atributo HttpOnly a la cookie '{name}'.",
                    "confidence": 0.90,
                })
            if is_https and not cookie.secure:
                findings.append({
                    "file_path": url,
                    "line_number": None,
                    "severity": "MEDIUM",
                    "category": "cookie_missing_secure",
                    "description": f"Cookie '{name}' sin atributo Secure en un sitio HTTPS",
                    "exploit_scenario": "La cookie puede transmitirse por HTTP sin cifrar.",
                    "recommendation": f"Añadir el atributo Secure a la cookie '{name}'.",
                    "confidence": 0.90,
                })
            samesite = getattr(cookie, "_rest", {}).get("SameSite") or ""
            if not samesite:
                findings.append({
                    "file_path": url,
                    "line_number": None,
                    "severity": "LOW",
                    "category": "cookie_missing_samesite",
                    "description": f"Cookie '{name}' sin atributo SameSite",
                    "exploit_scenario": "Aumenta el riesgo de ataques CSRF.",
                    "recommendation": f"Añadir SameSite=Lax o SameSite=Strict a la cookie '{name}'.",
                    "confidence": 0.85,
                })

        # --- CSRF check (basic: look for forms without hidden CSRF token) ---
        if _BS4:
            soup = BeautifulSoup(resp.text, "html.parser")
            for form in soup.find_all("form"):
                method = form.get("method", "get").lower()
                if method == "post":
                    hidden_inputs = form.find_all("input", type="hidden")
                    has_csrf = any(
                        "csrf" in (inp.get("name", "") + inp.get("id", "")).lower()
                        for inp in hidden_inputs
                    )
                    if not has_csrf:
                        findings.append({
                            "file_path": url,
                            "line_number": None,
                            "severity": "MEDIUM",
                            "category": "missing_csrf_protection",
                            "description": "Formulario POST sin token CSRF visible",
                            "exploit_scenario": "Un atacante puede inducir a un usuario autenticado a enviar el formulario desde otro dominio.",
                            "recommendation": "Implementar tokens CSRF en todos los formularios POST.",
                            "confidence": 0.75,
                        })
                        break

    except RequestException as e:
        print(f"[WARN] HTTP request failed: {e}")

    # --- TLS inspection ---
    if is_https and hostname:
        tls_findings = _check_tls(hostname)
        findings.extend(tls_findings)

    # --- Exposed path probing (passive GET, no exploitation) ---
    base = f"{parsed.scheme}://{parsed.netloc}"
    for probe_path in EXPOSED_PATH_PROBES:
        try:
            probe_resp = requests.get(
                base + probe_path, timeout=8, allow_redirects=False,
                headers={"User-Agent": "Mozilla/5.0 (security-audit/1.0)"}
            )
            if probe_resp.status_code == 200 and len(probe_resp.text) > 50:
                category = "exposed_env_file" if ".env" in probe_path else \
                           "exposed_git_config" if ".git" in probe_path else \
                           "exposed_admin_panel" if "admin" in probe_path.lower() or "wp-" in probe_path else \
                           "exposed_debug_endpoint"
                severity = "HIGH" if ".env" in probe_path or ".git" in probe_path else "MEDIUM"
                findings.append({
                    "file_path": base + probe_path,
                    "line_number": None,
                    "severity": severity,
                    "category": category,
                    "description": f"Recurso sensible accesible públicamente: {probe_path}",
                    "exploit_scenario": f"El archivo {probe_path} está expuesto y puede contener credenciales o configuración sensible.",
                    "recommendation": f"Bloquear el acceso a {probe_path} en la configuración del servidor web.",
                    "confidence": 0.90,
                })
        except Exception:
            pass

    summary = {
        "total": len(findings),
        "high": sum(1 for f in findings if f["severity"] == "HIGH"),
        "medium": sum(1 for f in findings if f["severity"] == "MEDIUM"),
        "low": sum(1 for f in findings if f["severity"] == "LOW"),
        "files_reviewed": 1,
        "scan_mode": "public_url",
    }

    print(f"[INFO] Public URL scan complete — {len(findings)} findings.")
    return {"findings": findings, "analysis_summary": summary}


# ---------------------------------------------------------------------------
# PRE-LAUNCH scan mode
# ---------------------------------------------------------------------------

def scan_pre_launch(target_path: Path, client_slug: str) -> dict:
    """
    Static analysis of a generated HTML/CSS/JS bundle.
    Checks for: eval(), innerHTML, hardcoded secrets, missing CSP meta,
    HTTP links in HTTPS page, unsafe form actions.
    """
    print(f"[INFO] Starting pre-launch static scan: {target_path}")
    findings: list[dict] = []

    html_files = [target_path] if target_path.is_file() else list(target_path.rglob("*.html")) + list(target_path.rglob("*.htm"))
    js_files = [] if target_path.is_file() else list(target_path.rglob("*.js"))
    all_files = html_files + js_files

    for filepath in all_files:
        if not filepath.exists():
            continue
        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(filepath.relative_to(target_path.parent if target_path.is_file() else target_path))

        # eval() usage
        for match in re.finditer(r'\beval\s*\(', source):
            line_no = source[:match.start()].count("\n") + 1
            findings.append({
                "file_path": rel,
                "line_number": line_no,
                "severity": "HIGH",
                "category": "eval_injection",
                "description": "Uso de eval() detectado — riesgo de inyección de código",
                "exploit_scenario": "Si algún argumento de eval() puede ser controlado por el usuario, se puede ejecutar código arbitrario.",
                "recommendation": "Eliminar eval(). Usar JSON.parse() para datos, o reestructurar la lógica.",
                "confidence": 0.80,
            })
            break

        # innerHTML assignments
        for match in re.finditer(r'\.innerHTML\s*=', source):
            line_no = source[:match.start()].count("\n") + 1
            findings.append({
                "file_path": rel,
                "line_number": line_no,
                "severity": "MEDIUM",
                "category": "innerHTML_assignment",
                "description": "Asignación a innerHTML detectada — riesgo de XSS",
                "exploit_scenario": "Si el valor asignado incluye datos del usuario sin sanear, se puede inyectar HTML/JS malicioso.",
                "recommendation": "Usar textContent en lugar de innerHTML, o sanitizar con DOMPurify.",
                "confidence": 0.70,
            })
            break

        # Hardcoded secrets
        for pattern, desc in SECRET_PATTERNS:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                line_no = source[:match.start()].count("\n") + 1
                findings.append({
                    "file_path": rel,
                    "line_number": line_no,
                    "severity": "HIGH",
                    "category": "hardcoded_secret",
                    "description": f"{desc} detectado en el código fuente del bundle",
                    "exploit_scenario": "Cualquier visitante puede extraer la clave del JS/HTML del bundle.",
                    "recommendation": "Mover las claves a variables de entorno del servidor. Nunca incrustar secretos en el frontend.",
                    "confidence": 0.85,
                })
                break

        # HTML-specific checks
        if filepath.suffix.lower() in (".html", ".htm"):
            if _BS4:
                soup = BeautifulSoup(source, "html.parser")

                # Missing CSP meta tag
                csp_meta = soup.find("meta", attrs={"http-equiv": re.compile(r"content-security-policy", re.I)})
                if not csp_meta:
                    findings.append({
                        "file_path": rel,
                        "line_number": None,
                        "severity": "MEDIUM",
                        "category": "missing_csp",
                        "description": "No se encontró meta Content-Security-Policy en el HTML",
                        "exploit_scenario": "Sin CSP, el navegador no restringe qué recursos puede cargar la página.",
                        "recommendation": "Añadir <meta http-equiv='Content-Security-Policy' content='...'> en el <head>.",
                        "confidence": 0.90,
                    })

                # Forms with non-HTTPS action
                for form in soup.find_all("form", action=True):
                    action = form["action"]
                    if action.startswith("http://"):
                        findings.append({
                            "file_path": rel,
                            "line_number": None,
                            "severity": "HIGH",
                            "category": "form_non_https_action",
                            "description": f"Formulario con action HTTP no cifrado: {action}",
                            "exploit_scenario": "Los datos del formulario se transmiten en texto claro, susceptibles de interceptación.",
                            "recommendation": "Cambiar el action del formulario a HTTPS.",
                            "confidence": 0.95,
                        })

                # HTTP resources on what should be HTTPS page
                http_resources = []
                for tag in soup.find_all(["script", "link", "img", "iframe"]):
                    src = tag.get("src") or tag.get("href") or ""
                    if src.startswith("http://"):
                        http_resources.append(src)
                if http_resources:
                    findings.append({
                        "file_path": rel,
                        "line_number": None,
                        "severity": "LOW",
                        "category": "http_resource_on_https_page",
                        "description": f"Recursos externos cargados por HTTP ({len(http_resources)} encontrados)",
                        "exploit_scenario": "Los recursos HTTP en páginas HTTPS generan advertencias de contenido mixto y pueden ser interceptados.",
                        "recommendation": "Reemplazar todas las URLs de recursos externos para que usen HTTPS.",
                        "confidence": 0.90,
                    })
            else:
                # Fallback regex check for CSP meta
                if "content-security-policy" not in source.lower():
                    findings.append({
                        "file_path": rel,
                        "line_number": None,
                        "severity": "MEDIUM",
                        "category": "missing_csp",
                        "description": "No se encontró meta Content-Security-Policy en el HTML",
                        "exploit_scenario": "Sin CSP, el navegador no restringe los recursos que puede cargar la página.",
                        "recommendation": "Añadir <meta http-equiv='Content-Security-Policy' content='...'> en el <head>.",
                        "confidence": 0.85,
                    })

    summary = {
        "total": len(findings),
        "high": sum(1 for f in findings if f["severity"] == "HIGH"),
        "medium": sum(1 for f in findings if f["severity"] == "MEDIUM"),
        "low": sum(1 for f in findings if f["severity"] == "LOW"),
        "files_reviewed": len(all_files),
        "scan_mode": "pre_launch",
    }

    print(f"[INFO] Pre-launch scan complete — {len(findings)} findings across {len(all_files)} files.")
    return {"findings": findings, "analysis_summary": summary}


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------

def write_findings(
    client_slug: str,
    target: str,
    contract_path,
    results: dict,
    scan_mode: str = "repo",
) -> Path:
    """Write findings.json (with compliance fields) and print a summary."""
    out_dir = PROJECT_ROOT / "output" / "audits" / client_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "findings.json"

    findings = results.get("findings", [])
    summary = results.get("analysis_summary", {})

    # Enrich with compliance mapping
    findings = enrich_compliance(findings)

    output = {
        "client_slug": client_slug,
        "target": target,
        "scan_mode": scan_mode,
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
    print(f"AUDIT COMPLETE — {client_slug} [{scan_mode}]")
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
    parser.add_argument("--target", required=True,
                        help="GitHub URL, live URL, or local path to audit")
    parser.add_argument("--client-slug", required=True,
                        help="Client identifier for output paths (e.g. acme-corp)")
    parser.add_argument("--scan-mode", default="repo",
                        choices=["repo", "public_url", "pre_launch"],
                        help="Scan mode: repo (default), public_url, or pre_launch")
    parser.add_argument("--contract-path",
                        help="Override default authorization contract path")
    parser.add_argument("--skip-contract", action="store_true",
                        help="Skip authorization check — ONLY for self-audits or pre_launch")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"WAT SECURITY AUDIT — {args.client_slug} [{args.scan_mode}]")
    print(f"{'='*60}\n")

    # Authorization gate (all modes require it unless --skip-contract)
    if args.skip_contract:
        print("[WARN] --skip-contract set. Skipping authorization check.")
        contract_path = "N/A — self-audit / pre-launch"
    else:
        explicit_path = Path(args.contract_path) if args.contract_path else None
        contract_path = verify_authorization(args.client_slug, explicit_path)

    # Dispatch by scan mode
    if args.scan_mode == "public_url":
        results = scan_public_url(args.target, args.client_slug)

    elif args.scan_mode == "pre_launch":
        local_path, _ = resolve_target(args.target, args.client_slug)
        results = scan_pre_launch(local_path, args.client_slug)

    else:  # repo
        local_path, was_cloned = resolve_target(args.target, args.client_slug)
        print(f"[INFO] Collecting scannable files from {local_path} ...")
        files = collect_files(local_path)
        print(f"[INFO] Found {len(files)} scannable files.")
        if not files:
            print("[ERROR] No scannable files found. Check the target path.")
            sys.exit(1)
        codebase_context = build_codebase_context(files)
        results = run_audit(args.target, codebase_context)
        if was_cloned:
            shutil.rmtree(local_path, ignore_errors=True)
            print("[INFO] Cleaned up temporary clone.")

    # Write output
    out_file = write_findings(
        args.client_slug, args.target, contract_path, results, scan_mode=args.scan_mode
    )

    print(f"[DONE] Findings: {out_file}")
    if args.scan_mode == "repo":
        print(f"       Next step: render report using tools/generate_audit_pdf.py\n")


if __name__ == "__main__":
    main()
