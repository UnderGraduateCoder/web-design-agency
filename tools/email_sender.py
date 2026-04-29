"""
email_sender.py

Shared email infrastructure for all Cifra skills.

Usage:
    from tools.email_sender import send_email

    send_email(
        to="cliente@empresa.es",
        subject="Tu propuesta de web",
        body_html="<p>Hola...</p>",
        dry_run=True,   # set False to actually send
    )

Credentials (read from .env):
    RESEND_API_KEY          — preferred sender (Resend transactional API)
    SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS  — fallback SMTP

Rate limit: 50 emails per sender identity per calendar day.
Every send (real or dry-run) is appended to data/email_log.jsonl.
No email body is written to the log — only metadata.
"""

import json
import os
import smtplib
import sys
from datetime import date, datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import urllib.request as _urllib_request
except ImportError:
    _urllib_request = None

PROJECT_ROOT = Path(__file__).parent.parent
LOG_PATH = PROJECT_ROOT / "data" / "email_log.jsonl"

DAILY_RATE_LIMIT = 50

GDPR_FOOTER = """
<hr style="margin:32px 0;border:none;border-top:1px solid #e5e7eb;">
<p style="font-size:12px;color:#6b7280;margin:0;">
  <strong>Cifra</strong> — Agencia Web · Valencia, España<br>
  Si no deseas recibir más comunicaciones, responde a este email con el asunto
  <em>BAJA</em> o escríbenos a <a href="mailto:adrianarconroyo@gmail.com">adrianarconroyo@gmail.com</a>.<br>
  Este mensaje se envía conforme al Reglamento General de Protección de Datos (RGPD/GDPR).
</p>
"""


class RateLimitError(Exception):
    pass


class EmailConfigError(Exception):
    pass


def _load_config() -> dict:
    """Return active sender config dict. Raises EmailConfigError if nothing is configured."""
    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    if resend_key:
        return {"mode": "resend", "key": resend_key}

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASS", "").strip()
    if smtp_host and smtp_user:
        return {
            "mode": "smtp",
            "host": smtp_host,
            "port": int(os.getenv("SMTP_PORT", "465")),
            "user": smtp_user,
            "password": smtp_pass,
        }

    raise EmailConfigError(
        "No email credentials found. Set RESEND_API_KEY or SMTP_HOST/SMTP_USER/SMTP_PASS in .env"
    )


def _sender_identity(config: dict) -> str:
    """Return a stable string identifying the sending account for rate-limit bucketing."""
    if config["mode"] == "resend":
        return f"resend:{config['key'][:8]}"
    return f"smtp:{config['user']}"


def _count_today_sends(sender_key: str) -> int:
    """Count emails sent today by this sender from the log file."""
    if not LOG_PATH.exists():
        return 0
    today = date.today().isoformat()
    count = 0
    with LOG_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("sender") == sender_key and record.get("ts", "").startswith(today):
                    count += 1
            except (json.JSONDecodeError, KeyError):
                continue
    return count


def _log_send(record: dict) -> None:
    """Append one JSON record to data/email_log.jsonl. Never logs email body."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _build_html(body_html: str) -> str:
    """Wrap body with GDPR footer."""
    return body_html + GDPR_FOOTER


def _send_via_resend(config: dict, to: str, subject: str, html: str, attachments: list) -> None:
    if _urllib_request is None:
        raise EmailConfigError("urllib.request not available")

    payload = {
        "from": "Cifra <onboarding@resend.dev>",
        "to": [to],
        "subject": subject,
        "html": html,
    }
    data = json.dumps(payload).encode("utf-8")
    req = _urllib_request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {config['key']}",
            "Content-Type": "application/json",
            "User-Agent": "cifra-mailer/1.0",
        },
        method="POST",
    )
    try:
        with _urllib_request.urlopen(req, timeout=15) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"Resend API error {resp.status}: {resp.read().decode()}")
    except Exception as exc:
        raise RuntimeError(f"Resend send failed: {exc}") from exc


def _send_via_smtp(config: dict, to: str, subject: str, html: str, attachments: list) -> None:
    msg = MIMEMultipart("mixed")
    msg["From"] = f"Cifra <{config['user']}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html", "utf-8"))

    for path in attachments:
        p = Path(path)
        if p.exists():
            with p.open("rb") as fh:
                part = MIMEApplication(fh.read(), Name=p.name)
            part["Content-Disposition"] = f'attachment; filename="{p.name}"'
            msg.attach(part)

    with smtplib.SMTP_SSL(config["host"], config["port"]) as server:
        server.login(config["user"], config["password"])
        server.sendmail(config["user"], [to], msg.as_string())


def send_email(
    to: str,
    subject: str,
    body_html: str,
    attachments: list = None,
    dry_run: bool = False,
) -> dict:
    """
    Send a single transactional email.

    Parameters
    ----------
    to          : recipient email address
    subject     : email subject line
    body_html   : HTML body (GDPR footer is appended automatically)
    attachments : optional list of local file paths to attach
    dry_run     : if True, log intent but do not actually send

    Returns a dict with send metadata.
    Raises RateLimitError if the daily cap is exceeded.
    Raises EmailConfigError if no credentials are configured.
    """
    if attachments is None:
        attachments = []

    if dry_run:
        # In dry-run mode credentials are optional — use a placeholder sender key.
        try:
            config = _load_config()
            sender_key = _sender_identity(config)
        except EmailConfigError:
            config = None
            sender_key = "dry_run:unconfigured"
    else:
        config = _load_config()
        sender_key = _sender_identity(config)

    sent_today = _count_today_sends(sender_key)
    if sent_today >= DAILY_RATE_LIMIT:
        raise RateLimitError(
            f"Daily email limit of {DAILY_RATE_LIMIT} reached for sender '{sender_key}'. "
            f"Wait until tomorrow or use a different sender."
        )

    html = _build_html(body_html)
    ts = datetime.now(timezone.utc).isoformat()

    record = {
        "ts": ts,
        "sender": sender_key,
        "to": to,
        "subject": subject,
        "status": "dry_run" if dry_run else "sent",
        "dry_run": dry_run,
    }

    if not dry_run:
        try:
            if config["mode"] == "resend":
                _send_via_resend(config, to, subject, html, attachments)
            else:
                _send_via_smtp(config, to, subject, html, attachments)
        except Exception as exc:
            record["status"] = "error"
            record["error"] = str(exc)
            _log_send(record)
            raise

    _log_send(record)
    return record


if __name__ == "__main__":
    # Quick dry-run smoke test
    result = send_email(
        to="test@example.com",
        subject="Test — Cifra email_sender",
        body_html="<p>Este es un mensaje de prueba.</p>",
        dry_run=True,
    )
    print(json.dumps(result, indent=2))
    assert result["dry_run"] is True
    print("[OK] email_sender dry-run passed.", file=sys.stderr)
