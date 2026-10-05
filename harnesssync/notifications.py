"""Email delivery for feedback submissions and session-time reports.

Uses Gmail SMTP with an app password. Configure in `.streamlit/secrets.toml`:

    [email]
    address = "you@gmail.com"
    app_password = "xxxx xxxx xxxx xxxx"
    to_address = "you@gmail.com"   # optional, defaults to `address`

Never raises - a missing/broken email config should never lose a feedback
submission or block the app. Data is always saved to disk first; email is a
best-effort notification on top of that, not the source of truth.
"""

import smtplib
from email.mime.text import MIMEText

import streamlit as st

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def _get_email_secrets():
    try:
        return st.secrets.get("email", {})
    except Exception:
        return {}


def is_configured() -> bool:
    secrets = _get_email_secrets()
    return bool(secrets.get("address") and secrets.get("app_password"))


def send_email(subject, body) -> bool:
    """Best-effort send. Returns True on success, False otherwise (including
    when email isn't configured at all - that's a no-op, not an error)."""
    secrets = _get_email_secrets()
    address = secrets.get("address")
    app_password = secrets.get("app_password")
    if not address or not app_password:
        return False

    to_address = secrets.get("to_address", address)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = address
    msg["To"] = to_address

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.login(address, app_password)
            server.sendmail(address, [to_address], msg.as_string())
        return True
    except Exception:
        return False
