"""Verified email/password identities, independent of Google OAuth.

Only a code delivered to the mailbox can create or reset its password. Existing
profile keys are retained; knowing an email alone never grants its climbing log.
"""
import hashlib
import hmac
import re
import secrets
import time

import sqlalchemy as sa

from harnesssync.db_store import get_db, password_accounts as accounts, profiles
from harnesssync.support_store import insert_once, lock_account
from harnesssync import notifications

ITERATIONS = 600_000
SESSION_SECONDS = 12 * 60 * 60


def normalize_email(email):
    email = email.strip().casefold()
    if len(email) > 254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", email):
        raise ValueError("Enter a valid email address.")
    return email


def _hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"{salt}${digest}"


def _matches(password, encoded):
    salt, _, _digest = encoded.partition("$")
    # Unknown accounts still perform the expensive password derivation.
    candidate = _hash(password, salt or "0" * 32)
    return bool(encoded) and hmac.compare_digest(candidate, encoded)


def _code_hash(code):
    return hashlib.sha256(code.strip().encode()).hexdigest()


def request_code(email, *, now=None):
    """Send a single-use setup/reset code. Never returns or logs the code."""
    email = normalize_email(email)
    now = int(time.time() if now is None else now)
    if not notifications.is_configured():
        raise ValueError("Account email delivery isn't configured yet. Please use the support link.")
    code = secrets.token_hex(8)
    with get_db() as conn:
        lock_account(conn, "password:" + email)
        insert_once(conn, accounts, {"email": email})
        row = conn.execute(sa.select(accounts).where(accounts.c.email == email)).mappings().one()
        if now - row["last_sent"] < 60:
            raise ValueError("Wait a minute before requesting another code.")
        conn.execute(accounts.update().where(accounts.c.email == email).values(
            code_hash=_code_hash(code), code_expires=now + 600, code_attempts=0, last_sent=now))
    delivered = notifications.send_email(
        "HarnessSync password verification",
        f"Your HarnessSync verification code is: {code}\n\n"
        "It expires in 10 minutes. Use it only on HarnessSync to set your password. "
        "If you didn't request it, ignore this email; your password has not changed.",
        recipient=email,
    )
    if not delivered:
        raise ValueError("We couldn't send the email. Please try again in a minute or use the support link.")


def set_password(email, code, password, *, now=None):
    email = normalize_email(email)
    if not 12 <= len(password) <= 128:
        raise ValueError("Use a password between 12 and 128 characters.")
    now = int(time.time() if now is None else now)
    encoded = _hash(password)
    valid = False
    with get_db() as conn:
        lock_account(conn, "password:" + email)
        row = conn.execute(sa.select(accounts).where(accounts.c.email == email)).mappings().first()
        if row and row["code_hash"] and row["code_expires"] > now and row["code_attempts"] < 5:
            valid = hmac.compare_digest(_code_hash(code), row["code_hash"])
            if not valid:
                conn.execute(accounts.update().where(accounts.c.email == email).values(
                    code_attempts=row["code_attempts"] + 1))
            else:
                existing = conn.execute(sa.select(profiles.c.user_id).where(
                    sa.func.lower(profiles.c.user_id) == email)).scalars().all()
                if len(existing) > 1:
                    raise ValueError("Please contact support to connect this existing account.")
                user_id = row["user_id"] or (existing[0] if existing else email)
                conn.execute(accounts.update().where(accounts.c.email == email).values(
                    user_id=user_id, password_hash=encoded, revision=secrets.token_hex(32),
                    code_hash="", code_expires=0, code_attempts=0, failures=0, locked_until=0))
    if not valid:
        raise ValueError("Invalid or expired code. Request a new code if needed.")


def sign_in(email, password, *, now=None):
    email = normalize_email(email)
    if len(password) > 128:
        return None
    now = int(time.time() if now is None else now)
    with get_db() as conn:
        lock_account(conn, "password:" + email)
        insert_once(conn, accounts, {"email": email})
        row = conn.execute(sa.select(accounts).where(accounts.c.email == email)).mappings().one()
        if row["locked_until"] > now:
            return None
        if not _matches(password, row["password_hash"]):
            failures = row["failures"] + 1
            conn.execute(accounts.update().where(accounts.c.email == email).values(
                failures=0 if failures >= 5 else failures,
                locked_until=now + 900 if failures >= 5 else 0))
            return None
        conn.execute(accounts.update().where(accounts.c.email == email).values(failures=0, locked_until=0))
        return {"email": email, "user_id": row["user_id"], "revision": row["revision"],
                "expires": now + SESSION_SECONDS}


def session_user(session, *, now=None):
    """Server-side session state only; reset passwords invalidate prior sessions."""
    now = int(time.time() if now is None else now)
    if not session or session.get("expires", 0) <= now:
        return None
    with get_db() as conn:
        row = conn.execute(sa.select(accounts).where(
            accounts.c.email == session.get("email"))).mappings().first()
        if row and row["password_hash"] and hmac.compare_digest(row["revision"], session.get("revision", "")):
            return row["user_id"]
    return None
