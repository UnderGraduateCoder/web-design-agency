"""
db.py

Usage:
    python tools/db.py --init          # Initialize database and tables
    python tools/db.py --seed          # Initialize + seed services catalog
    python tools/db.py --add-test-client  # Add a sample client for testing

Manages the local encrypted SQLite database at data/clients.db.
Encryption key is read from DB_ENCRYPTION_KEY in .env.

If sqlcipher3 is not available (requires SQLCipher DLLs), falls back to
standard sqlite3 with a warning — database will be unencrypted locally.

SECURITY: Never log client data to stdout or any file outside data/.
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import date, datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# SQLCipher / sqlite3 backend selection
# ---------------------------------------------------------------------------

try:
    import sqlcipher3
    _sqlite = sqlcipher3
    _ENCRYPTED = True
except ImportError:
    import sqlite3 as _sqlite
    _ENCRYPTED = False
    print(
        "[WARN] sqlcipher3 not installed — database will be stored unencrypted. "
        "Install SQLCipher and run: pip install sqlcipher3",
        file=sys.stderr,
    )

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "clients.db"


def _get_key() -> str:
    key = os.getenv("DB_ENCRYPTION_KEY", "")
    if not key and _ENCRYPTED:
        print(
            "[ERROR] DB_ENCRYPTION_KEY not set in .env — cannot open encrypted database.",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def _connect():
    """Open a connection to the database, applying the encryption key if available."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _sqlite.connect(str(DB_PATH))
    if _ENCRYPTED:
        key = _get_key()
        conn.execute(f"PRAGMA key='{key}'")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = _sqlite.Row
    return conn


def _set_permissions():
    """Restrict DB file to owner-only on Unix. Uses icacls on Windows."""
    if not DB_PATH.exists():
        return
    if os.name == "nt":
        try:
            username = os.environ.get("USERNAME", "")
            if username:
                subprocess.run(
                    ["icacls", str(DB_PATH), "/inheritance:r",
                     "/grant:r", f"{username}:(R,W)"],
                    capture_output=True,
                )
        except Exception:
            pass
    else:
        os.chmod(DB_PATH, 0o600)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug                        TEXT NOT NULL UNIQUE,
    business_name               TEXT NOT NULL,
    contact_email               TEXT,
    contact_phone               TEXT,
    address                     TEXT,
    tier                        TEXT NOT NULL CHECK(tier IN ('basic','pro','premium','enterprise')),
    website_price               REAL,
    monthly_hosting_fee         REAL,
    monthly_security_fee        REAL,
    monthly_total               REAL GENERATED ALWAYS AS (
                                    COALESCE(monthly_hosting_fee, 0) +
                                    COALESCE(monthly_security_fee, 0)
                                ) STORED,
    contract_start_date         TEXT,
    contract_end_date           TEXT,
    next_billing_date           TEXT,
    authorization_contract_path TEXT,
    website_output_path         TEXT,
    notes                       TEXT,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS services_catalog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    service_code    TEXT NOT NULL UNIQUE,
    service_name_es TEXT NOT NULL,
    description_es  TEXT,
    pricing_model   TEXT NOT NULL CHECK(pricing_model IN ('one_time','monthly','per_change','per_finding')),
    base_price      REAL NOT NULL,
    min_price       REAL,
    max_price       REAL
);

CREATE TABLE IF NOT EXISTS client_services (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    service_code TEXT NOT NULL REFERENCES services_catalog(service_code),
    custom_price REAL,
    active       INTEGER NOT NULL DEFAULT 1,
    start_date   TEXT,
    end_date     TEXT
);

CREATE TABLE IF NOT EXISTS audits (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id            INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    scan_date            TEXT NOT NULL DEFAULT (datetime('now')),
    scan_type            TEXT NOT NULL CHECK(scan_type IN ('repo','public_url','website_build')),
    findings_json_path   TEXT,
    report_pdf_path      TEXT,
    total_findings       INTEGER DEFAULT 0,
    high                 INTEGER DEFAULT 0,
    medium               INTEGER DEFAULT 0,
    low                  INTEGER DEFAULT 0,
    compliance_flags_json TEXT
);

CREATE TABLE IF NOT EXISTS change_requests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id        INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    requested_at     TEXT NOT NULL DEFAULT (datetime('now')),
    description_es   TEXT NOT NULL,
    estimated_hours  REAL,
    price            REAL,
    status           TEXT NOT NULL DEFAULT 'pending'
                         CHECK(status IN ('pending','in_progress','completed','cancelled')),
    completed_at     TEXT
);

CREATE TABLE IF NOT EXISTS billing_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    period_start    TEXT NOT NULL,
    period_end      TEXT NOT NULL,
    line_items_json TEXT,
    total           REAL NOT NULL,
    paid            INTEGER NOT NULL DEFAULT 0,
    invoice_path    TEXT
);

CREATE TABLE IF NOT EXISTS leads (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name      TEXT NOT NULL,
    region             TEXT,
    sector             TEXT,
    phone              TEXT,
    email              TEXT,
    website            TEXT,
    website_status     TEXT,
    score              REAL,
    first_contacted_at TEXT,
    status             TEXT NOT NULL DEFAULT 'new'
                           CHECK(status IN ('new','contacted','demo_sent','in_conversation','won','lost')),
    notes              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outreach_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id       INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    email_address TEXT,
    subject       TEXT,
    body          TEXT,
    sent_at       TEXT NOT NULL DEFAULT (datetime('now')),
    opened_at     TEXT,
    replied_at    TEXT
);

CREATE TABLE IF NOT EXISTS competitors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    competitor_url  TEXT NOT NULL,
    added_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS competitor_scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id   INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    scan_date       TEXT NOT NULL DEFAULT (datetime('now')),
    scan_data_json  TEXT,
    report_pdf_path TEXT
);

CREATE TABLE IF NOT EXISTS blog_posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    slug            TEXT NOT NULL,
    published_at    TEXT,
    word_count      INTEGER,
    hero_image_path TEXT,
    status          TEXT NOT NULL DEFAULT 'draft'
                        CHECK(status IN ('draft','published','archived'))
);

CREATE TABLE IF NOT EXISTS ab_tests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    test_name   TEXT NOT NULL,
    variant_a   TEXT,
    variant_b   TEXT,
    status      TEXT NOT NULL DEFAULT 'running'
                    CHECK(status IN ('running','ended')),
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at    TEXT,
    winner      TEXT
);

CREATE TABLE IF NOT EXISTS ab_test_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id    INTEGER NOT NULL REFERENCES ab_tests(id) ON DELETE CASCADE,
    client_id  INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    variant    TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp  TEXT NOT NULL DEFAULT (datetime('now')),
    session_id TEXT
);

CREATE TABLE IF NOT EXISTS social_content_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    week_of_year    INTEGER NOT NULL,
    generation_date TEXT NOT NULL DEFAULT (datetime('now')),
    post_count      INTEGER DEFAULT 0,
    output_path     TEXT
);
"""

_UPDATED_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS clients_updated_at
AFTER UPDATE ON clients
BEGIN
    UPDATE clients SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create the database, apply schema, and set restrictive file permissions."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.executescript(_UPDATED_TRIGGER)
        for stmt in [
            "ALTER TABLE services_catalog ADD COLUMN tier_restriction TEXT",
            "ALTER TABLE clients ADD COLUMN contract_sent_at TEXT",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass  # column already exists
    _set_permissions()


def log_contract_sent(client_id: int) -> None:
    """Record when contracts were sent to the client."""
    with _connect() as conn:
        conn.execute(
            "UPDATE clients SET contract_sent_at = datetime('now') WHERE id = ?",
            (client_id,),
        )


def add_client(
    slug: str,
    business_name: str,
    tier: str,
    *,
    contact_email: str = None,
    contact_phone: str = None,
    address: str = None,
    website_price: float = None,
    monthly_hosting_fee: float = None,
    monthly_security_fee: float = None,
    contract_start_date: str = None,
    contract_end_date: str = None,
    next_billing_date: str = None,
    authorization_contract_path: str = None,
    website_output_path: str = None,
    notes: str = None,
) -> int:
    """Insert a new client. Returns the new row id."""
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO clients
               (slug, business_name, tier, contact_email, contact_phone, address,
                website_price, monthly_hosting_fee, monthly_security_fee,
                contract_start_date, contract_end_date, next_billing_date,
                authorization_contract_path, website_output_path, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (slug, business_name, tier, contact_email, contact_phone, address,
             website_price, monthly_hosting_fee, monthly_security_fee,
             contract_start_date, contract_end_date, next_billing_date,
             authorization_contract_path, website_output_path, notes),
        )
        return cur.lastrowid


def get_client(slug: str) -> dict | None:
    """Return client row as dict, or None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE slug = ?", (slug,)
        ).fetchone()
    return dict(row) if row else None


def update_client_tier(slug: str, tier: str) -> None:
    """Change a client's tier."""
    with _connect() as conn:
        conn.execute(
            "UPDATE clients SET tier = ? WHERE slug = ?", (tier, slug)
        )


def add_audit(
    client_slug: str,
    scan_type: str,
    findings_json_path: str = None,
    report_pdf_path: str = None,
    total_findings: int = 0,
    high: int = 0,
    medium: int = 0,
    low: int = 0,
    compliance_flags: dict = None,
) -> int:
    """Record an audit run for a client. Returns new audit id."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE slug = ?", (client_slug,)
        ).fetchone()
        if not row:
            raise ValueError(f"Client '{client_slug}' not found in database.")
        client_id = row["id"]
        flags_json = json.dumps(compliance_flags) if compliance_flags else None
        cur = conn.execute(
            """INSERT INTO audits
               (client_id, scan_type, findings_json_path, report_pdf_path,
                total_findings, high, medium, low, compliance_flags_json)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (client_id, scan_type, findings_json_path, report_pdf_path,
             total_findings, high, medium, low, flags_json),
        )
        return cur.lastrowid


def add_change_request(
    client_slug: str,
    description_es: str,
    estimated_hours: float = None,
    price: float = None,
) -> int:
    """Add a pending change request for a client. Returns new row id."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE slug = ?", (client_slug,)
        ).fetchone()
        if not row:
            raise ValueError(f"Client '{client_slug}' not found.")
        cur = conn.execute(
            """INSERT INTO change_requests
               (client_id, description_es, estimated_hours, price)
               VALUES (?,?,?,?)""",
            (row["id"], description_es, estimated_hours, price),
        )
        return cur.lastrowid


def log_billing(
    client_slug: str,
    period_start: str,
    period_end: str,
    line_items: list,
    total: float,
    paid: bool = False,
    invoice_path: str = None,
) -> int:
    """Record a billing period entry. Returns new row id."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE slug = ?", (client_slug,)
        ).fetchone()
        if not row:
            raise ValueError(f"Client '{client_slug}' not found.")
        cur = conn.execute(
            """INSERT INTO billing_history
               (client_id, period_start, period_end, line_items_json, total, paid, invoice_path)
               VALUES (?,?,?,?,?,?,?)""",
            (row["id"], period_start, period_end,
             json.dumps(line_items), total, 1 if paid else 0, invoice_path),
        )
        return cur.lastrowid


def export_client_report(slug: str) -> dict:
    """
    Return a complete client data dict with audit history and billing.
    Caller is responsible for writing this to a file — never logged to stdout.
    """
    with _connect() as conn:
        client = conn.execute(
            "SELECT * FROM clients WHERE slug = ?", (slug,)
        ).fetchone()
        if not client:
            raise ValueError(f"Client '{slug}' not found.")
        client_id = client["id"]

        audits = conn.execute(
            "SELECT * FROM audits WHERE client_id = ? ORDER BY scan_date DESC",
            (client_id,),
        ).fetchall()

        billing = conn.execute(
            "SELECT * FROM billing_history WHERE client_id = ? ORDER BY period_start DESC",
            (client_id,),
        ).fetchall()

        changes = conn.execute(
            "SELECT * FROM change_requests WHERE client_id = ? ORDER BY requested_at DESC",
            (client_id,),
        ).fetchall()

        services = conn.execute(
            """SELECT cs.*, sc.service_name_es, sc.pricing_model
               FROM client_services cs
               JOIN services_catalog sc ON cs.service_code = sc.service_code
               WHERE cs.client_id = ?""",
            (client_id,),
        ).fetchall()

    return {
        "client": dict(client),
        "audits": [dict(r) for r in audits],
        "billing_history": [dict(r) for r in billing],
        "change_requests": [dict(r) for r in changes],
        "services": [dict(r) for r in services],
    }


# ---------------------------------------------------------------------------
# Lead helpers
# ---------------------------------------------------------------------------

def add_lead(
    business_name: str,
    *,
    region: str = None,
    sector: str = None,
    phone: str = None,
    email: str = None,
    website: str = None,
    website_status: str = None,
    score: float = None,
    notes: str = None,
) -> int:
    """Insert a new lead. Returns the new row id."""
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO leads
               (business_name, region, sector, phone, email, website,
                website_status, score, notes)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (business_name, region, sector, phone, email, website,
             website_status, score, notes),
        )
        return cur.lastrowid


def update_lead_status(lead_id: int, status: str) -> None:
    """Update the pipeline status of a lead."""
    with _connect() as conn:
        conn.execute(
            "UPDATE leads SET status = ? WHERE id = ?", (status, lead_id)
        )


def get_leads_by_status(status: str) -> list:
    """Return all leads with the given status as a list of dicts."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM leads WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_lead_contacted(lead_id: int) -> None:
    """Set first_contacted_at (if not already set) and advance status to 'contacted'."""
    with _connect() as conn:
        conn.execute(
            """UPDATE leads
               SET status = 'contacted',
                   first_contacted_at = COALESCE(first_contacted_at, datetime('now'))
               WHERE id = ?""",
            (lead_id,),
        )


def log_lead_reply(lead_id: int, replied_at: str = None) -> None:
    """Mark the most recent outreach_log entry for this lead as replied."""
    ts = replied_at or datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """UPDATE outreach_log SET replied_at = ?
               WHERE lead_id = ? AND replied_at IS NULL
               ORDER BY sent_at DESC LIMIT 1""",
            (ts, lead_id),
        )
        conn.execute(
            "UPDATE leads SET status = 'in_conversation' WHERE id = ? AND status = 'contacted'",
            (lead_id,),
        )


def get_lead(lead_id: int) -> dict | None:
    """Return a lead row as a dict, or None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
    return dict(row) if row else None


def add_outreach_log(
    lead_id: int,
    email_address: str,
    subject: str,
    body: str,
) -> int:
    """Insert an outreach log entry. Returns the new row id."""
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO outreach_log (lead_id, email_address, subject, body)
               VALUES (?,?,?,?)""",
            (lead_id, email_address, subject, body),
        )
        return cur.lastrowid


def create_client_from_lead(lead_id: int, tier: str = "basic") -> int:
    """
    Promote a lead to a client. Copies lead data into the clients table.
    Returns the new client row id. Raises ValueError if lead not found.
    """
    import re as _re

    lead = get_lead(lead_id)
    if not lead:
        raise ValueError(f"Lead {lead_id} not found.")

    raw = lead["business_name"]
    slug = _re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")

    return add_client(
        slug=slug,
        business_name=raw,
        tier=tier,
        contact_email=lead.get("email"),
        contact_phone=lead.get("phone"),
        address=lead.get("region"),
        notes=lead.get("notes"),
    )


# ---------------------------------------------------------------------------
# Competitor helpers
# ---------------------------------------------------------------------------

def add_competitor(client_slug: str, competitor_url: str) -> int:
    """Add a competitor URL for a client. Returns new row id."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE slug = ?", (client_slug,)
        ).fetchone()
        if not row:
            raise ValueError(f"Client '{client_slug}' not found.")
        cur = conn.execute(
            "INSERT INTO competitors (client_id, competitor_url) VALUES (?,?)",
            (row["id"], competitor_url),
        )
        return cur.lastrowid


def list_competitors(client_slug: str) -> list:
    """Return all competitor rows for a client as a list of dicts."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE slug = ?", (client_slug,)
        ).fetchone()
        if not row:
            raise ValueError(f"Client '{client_slug}' not found.")
        rows = conn.execute(
            "SELECT * FROM competitors WHERE client_id = ? ORDER BY added_at DESC",
            (row["id"],),
        ).fetchall()
    return [dict(r) for r in rows]


def log_competitor_scan(
    competitor_id: int,
    scan_data: dict,
    report_pdf_path: str = None,
) -> int:
    """Record a competitor scan result. Returns new row id."""
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO competitor_scans
               (competitor_id, scan_data_json, report_pdf_path)
               VALUES (?,?,?)""",
            (competitor_id, json.dumps(scan_data), report_pdf_path),
        )
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Blog helpers
# ---------------------------------------------------------------------------

def add_blog_post(
    client_slug: str,
    title: str,
    slug: str,
    *,
    word_count: int = None,
    hero_image_path: str = None,
    status: str = "draft",
    published_at: str = None,
) -> int:
    """Create a blog post record for a client. Returns new row id."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE slug = ?", (client_slug,)
        ).fetchone()
        if not row:
            raise ValueError(f"Client '{client_slug}' not found.")
        cur = conn.execute(
            """INSERT INTO blog_posts
               (client_id, title, slug, published_at, word_count, hero_image_path, status)
               VALUES (?,?,?,?,?,?,?)""",
            (row["id"], title, slug, published_at, word_count, hero_image_path, status),
        )
        return cur.lastrowid


def list_blog_posts(client_slug: str) -> list:
    """Return all blog posts for a client as a list of dicts."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE slug = ?", (client_slug,)
        ).fetchone()
        if not row:
            raise ValueError(f"Client '{client_slug}' not found.")
        rows = conn.execute(
            "SELECT * FROM blog_posts WHERE client_id = ? ORDER BY published_at DESC",
            (row["id"],),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# A/B test helpers
# ---------------------------------------------------------------------------

def start_ab_test(
    client_slug: str,
    test_name: str,
    variant_a: str,
    variant_b: str,
) -> int:
    """Create a new running A/B test for a client. Returns new row id."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE slug = ?", (client_slug,)
        ).fetchone()
        if not row:
            raise ValueError(f"Client '{client_slug}' not found.")
        cur = conn.execute(
            """INSERT INTO ab_tests
               (client_id, test_name, variant_a, variant_b, status)
               VALUES (?,?,?,?,'running')""",
            (row["id"], test_name, variant_a, variant_b),
        )
        return cur.lastrowid


def log_ab_event(
    test_id: int,
    client_slug: str,
    variant: str,
    event_type: str,
    session_id: str = None,
) -> int:
    """Record a conversion event for an A/B test. Returns new row id."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE slug = ?", (client_slug,)
        ).fetchone()
        if not row:
            raise ValueError(f"Client '{client_slug}' not found.")
        cur = conn.execute(
            """INSERT INTO ab_test_events
               (test_id, client_id, variant, event_type, session_id)
               VALUES (?,?,?,?,?)""",
            (test_id, row["id"], variant, event_type, session_id),
        )
        return cur.lastrowid


def end_ab_test(test_id: int, winner: str) -> None:
    """Mark an A/B test as ended with the given winning variant."""
    with _connect() as conn:
        conn.execute(
            """UPDATE ab_tests
               SET status = 'ended', ended_at = datetime('now'), winner = ?
               WHERE id = ?""",
            (winner, test_id),
        )


def get_ab_test(test_id: int) -> dict | None:
    """Return a single A/B test row as a dict, or None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM ab_tests WHERE id = ?", (test_id,)
        ).fetchone()
    return dict(row) if row else None


def get_ab_test_events(test_id: int) -> list:
    """Return all events for an A/B test as a list of dicts."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ab_test_events WHERE test_id = ? ORDER BY timestamp ASC",
            (test_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_last_competitor_scan(competitor_id: int) -> dict | None:
    """Return the most recent scan row for a competitor, or None."""
    with _connect() as conn:
        row = conn.execute(
            """SELECT * FROM competitor_scans
               WHERE competitor_id = ?
               ORDER BY scan_date DESC LIMIT 1""",
            (competitor_id,),
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Social content helper
# ---------------------------------------------------------------------------

def log_social_generation(
    client_slug: str,
    week_of_year: int,
    post_count: int,
    output_path: str = None,
) -> int:
    """Record a social content generation run. Returns new row id."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE slug = ?", (client_slug,)
        ).fetchone()
        if not row:
            raise ValueError(f"Client '{client_slug}' not found.")
        cur = conn.execute(
            """INSERT INTO social_content_log
               (client_id, week_of_year, post_count, output_path)
               VALUES (?,?,?,?)""",
            (row["id"], week_of_year, post_count, output_path),
        )
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Services catalog seed data
# ---------------------------------------------------------------------------

_SERVICES_CATALOG = [
    # Website packages — one_time
    ("web_esencial",    "Paquete Web Esencial",    "Web de una página (one-pager) hasta 5 secciones, diseño responsive, formulario de contacto, animaciones básicas AOS. Entrega en 7 días.",                                                                             "one_time",   990.0,   990.0,    990.0),
    ("web_profesional", "Paquete Web Profesional", "Web completa hasta 6 páginas, animaciones 3D (GSAP + Lenis), imagen hero generada por IA, auditoría de seguridad pre-lanzamiento incluida, SEO básico on-page. Entrega en 14 días.",                                   "one_time",  2400.0,  2400.0,   2400.0),
    ("web_premium",     "Paquete Web Premium",     "Todo lo del Profesional más hasta 12 páginas, vídeo hero scroll-driven, sistema de diseño personalizado, integración CMS ligero, dashboard de analíticas. Entrega en 21 días.",                                         "one_time",  4800.0,  4800.0,   4800.0),
    ("web_enterprise",  "Paquete Web Enterprise",  "Proyecto a medida: aplicación web, e-commerce o portal de clientes. Integraciones API personalizadas, consultoría de marca incluida. Presupuesto cerrado tras briefing.",                                               "one_time",  8500.0,  8500.0,  25000.0),
    # Hosting & maintenance — monthly
    ("hosting_basico",  "Hosting Básico",          "Alojamiento en Vercel/Netlify, dominio .com/.es incluido, SSL automático, backups semanales, 99,9% uptime.",                                                                                                           "monthly",     29.0,    29.0,     29.0),
    ("hosting_pro",     "Hosting Pro",             "Todo lo del Básico más CDN premium, monitorización 24/7, backup diario, soporte por email en 24h.",                                                                                                                    "monthly",     59.0,    59.0,     59.0),
    ("hosting_premium", "Hosting Premium",         "Todo lo del Pro más soporte prioritario (respuesta en 4h) y 2 cambios menores al mes incluidos.",                                                                                                                       "monthly",    129.0,   129.0,    129.0),
    # Security services
    ("seg_auditoria_repo",   "Auditoría de Seguridad — Repositorio",    "Análisis estático completo del código fuente con IA. Informe PDF en español con hallazgos OWASP, ISO 27001 y RGPD. Precio por hallazgo según severidad.",                              "per_finding",  50.0,    50.0,    250.0),
    ("seg_auditoria_url",    "Auditoría de Seguridad — URL Pública",     "Análisis pasivo de cabeceras HTTP, TLS, endpoints expuestos y cookies. Informe PDF en español. Requiere contrato de autorización firmado.",                                             "one_time",   350.0,   350.0,    350.0),
    ("seg_prelanzamiento",   "Auditoría Pre-lanzamiento",                "Revisión de seguridad del bundle HTML/CSS/JS antes de la publicación. Incluida en los paquetes Profesional, Premium y Enterprise.",                                                    "one_time",   150.0,   150.0,    150.0),
    ("seg_retainer_basico",  "Retainer de Seguridad — Básico",           "Auditoría mensual de repositorio + informe de diferencias (hallazgos nuevos, resueltos y persistentes). Ideal para paquetes Esencial y Profesional.",                                   "monthly",     79.0,    79.0,     79.0),
    ("seg_retainer_pro",     "Retainer de Seguridad — Pro",              "Auditoría mensual de repositorio + URL pública + informe comparativo con mapeo RGPD. Incluido en paquete Hosting Premium.",                                                             "monthly",    149.0,   149.0,    149.0),
    ("cambio_menor",         "Cambio Menor de Contenido",                "Actualización de texto, imagen o enlace en una página existente. Plazo de entrega: 48h.",                                                                                               "per_change",  60.0,    60.0,     60.0),
    ("cambio_mayor",         "Cambio Mayor / Nueva Sección",             "Adición de nueva sección, página o funcionalidad al sitio existente. Presupuesto según estimación de horas.",                                                                           "per_change", 120.0,   120.0,    800.0),
    # Business development add-ons
    ("blog_mensual",         "Blog Mensual",                             "Redacción mensual de un artículo de blog optimizado para SEO (800-1200 palabras), con imagen hero generada por IA y publicación en el CMS del cliente.",                                    "monthly",     80.0,    80.0,     80.0),
    ("whatsapp_widget",      "Widget de WhatsApp",                       "Integración de botón flotante de WhatsApp en el sitio web. Configuración de mensaje de bienvenida personalizado. Instalación única.",                                                       "one_time",    50.0,    50.0,     50.0),
    ("whatsapp_autoreply",   "Autorespuesta de WhatsApp",                "Configuración de respuestas automáticas fuera de horario vía WhatsApp Business API. Incluye mantenimiento mensual del flujo de respuestas.",                                               "monthly",     15.0,    15.0,     15.0),
    ("ab_testing_setup",     "Configuración de A/B Testing",             "Diseño, implementación y análisis de tests A/B sobre secciones clave del sitio (hero, CTA, formulario). Informe de resultados con recomendación de variante ganadora. Solo plan Enterprise.", "one_time",   450.0,   450.0,    450.0),
    ("social_content_pack",  "Pack de Contenido Social",                 "Generación mensual de 12 publicaciones para redes sociales (Instagram, LinkedIn, Facebook) con copy adaptado a la marca y calendario editorial.",                                           "monthly",     90.0,    90.0,     90.0),
]


def seed_services_catalog() -> None:
    """Populate services_catalog with Cifra's full pricing structure."""
    init_db()
    with _connect() as conn:
        for row in _SERVICES_CATALOG:
            conn.execute(
                """INSERT OR IGNORE INTO services_catalog
                   (service_code, service_name_es, description_es, pricing_model,
                    base_price, min_price, max_price)
                   VALUES (?,?,?,?,?,?,?)""",
                row,
            )
        conn.execute(
            "UPDATE services_catalog SET tier_restriction = 'enterprise' "
            "WHERE service_code = 'ab_testing_setup'"
        )
    print(f"[OK] Seeded {len(_SERVICES_CATALOG)} services into catalog.", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _add_test_client() -> None:
    init_db()
    slug = "cliente-demo"
    existing = get_client(slug)
    if existing:
        print("[INFO] Test client already exists.", file=sys.stderr)
        return
    add_client(
        slug=slug,
        business_name="Empresa Demo S.L.",
        tier="pro",
        contact_email="demo@empresa.es",
        contact_phone="+34 600 000 000",
        address="Calle Mayor 1, 28001 Madrid",
        website_price=2400.0,
        monthly_hosting_fee=59.0,
        monthly_security_fee=79.0,
        contract_start_date=str(date.today()),
        next_billing_date=str(date.today().replace(day=1)),
        notes="Cliente de prueba — no facturar.",
    )
    print(f"[OK] Test client '{slug}' created.", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cifra client database manager")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--seed", action="store_true", help="Initialize + seed services catalog")
    parser.add_argument("--add-test-client", action="store_true", dest="test_client",
                        help="Add a sample client for testing")
    args = parser.parse_args()

    if args.seed:
        seed_services_catalog()
        print("[OK] Database initialized and catalog seeded.", file=sys.stderr)
    elif args.init:
        init_db()
        print("[OK] Database initialized.", file=sys.stderr)
    elif args.test_client:
        _add_test_client()
    else:
        parser.print_help()
