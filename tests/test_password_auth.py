"""Fictional mailboxes only: no network, hosted database or real credentials."""
import re

import pytest
import sqlalchemy as sa
from streamlit.testing.v1 import AppTest
from pathlib import Path

from harnesssync import db_store as db, password_auth as auth, profile_manager as pm

PASSWORD = "a fictional strong password"
NOW = 1_800_000_000


@pytest.fixture
def mailbox(tmp_path, monkeypatch):
    db.configure(f"sqlite:///{tmp_path / 'password.db'}")
    sent = []
    monkeypatch.setattr(auth.notifications, "is_configured", lambda: True)
    monkeypatch.setattr(auth.notifications, "send_email", lambda subject, body, **kw: sent.append((body, kw)) or True)
    yield sent
    db.get_engine().dispose()


def code_for(mailbox, email="alex@example.com", now=NOW):
    auth.request_code(email, now=now)
    assert mailbox[-1][1] == {"recipient": email.strip().lower()}
    return re.search(r"code is: ([a-f0-9]+)", mailbox[-1][0])[1]


def register(mailbox, email="alex@example.com", now=NOW):
    code = code_for(mailbox, email, now)
    auth.set_password(email, code, PASSWORD, now=now)


def test_mailbox_verification_preserves_existing_private_data(mailbox):
    pm.save_profile("Alex@Example.com", "Alex")
    pm.log_climb("Alex@Example.com", "Boulder", "V3", "Sent", "2026-01-01")
    assert auth.sign_in("alex@example.com", PASSWORD, now=NOW) is None
    code = code_for(mailbox)
    assert auth.sign_in("alex@example.com", PASSWORD, now=NOW) is None
    register_time = NOW + 1
    auth.set_password("alex@example.com", code, PASSWORD, now=register_time)
    session = auth.sign_in("ALEX@example.com", PASSWORD, now=register_time)
    assert auth.session_user(session, now=register_time) == "Alex@Example.com"
    assert len(pm.get_climbs(session["user_id"])) == 1
    register(mailbox, "blair@example.com")
    other = auth.sign_in("blair@example.com", PASSWORD, now=NOW)
    assert pm.get_climbs(auth.session_user(other, now=NOW)) == []
    with db.get_db() as conn:
        stored = conn.execute(sa.select(db.password_accounts).where(db.password_accounts.c.email == "alex@example.com")).mappings().one()
        assert PASSWORD not in stored["password_hash"]
        assert code not in stored["code_hash"]


def test_codes_expire_are_single_use_and_limit_guesses(mailbox):
    code = code_for(mailbox)
    with pytest.raises(ValueError, match="Wait"):
        auth.request_code("alex@example.com", now=NOW + 1)
    for _ in range(5):
        with pytest.raises(ValueError, match="Invalid"):
            auth.set_password("alex@example.com", "wrong", PASSWORD, now=NOW)
    with pytest.raises(ValueError, match="Invalid"):
        auth.set_password("alex@example.com", code, PASSWORD, now=NOW)
    code = code_for(mailbox, now=NOW + 61)
    with pytest.raises(ValueError, match="Invalid"):
        auth.set_password("alex@example.com", code, PASSWORD, now=NOW + 661)
    code = code_for(mailbox, now=NOW + 700)
    auth.set_password("alex@example.com", code, PASSWORD, now=NOW + 700)
    with pytest.raises(ValueError, match="Invalid"):
        auth.set_password("alex@example.com", code, PASSWORD, now=NOW + 701)


def test_reset_revokes_sessions_and_does_not_change_password_before_verification(mailbox):
    register(mailbox)
    session = auth.sign_in("alex@example.com", PASSWORD, now=NOW)
    code = code_for(mailbox, now=NOW + 61)
    assert auth.session_user(session, now=NOW + 61)
    auth.set_password("alex@example.com", code, "a different fictional password", now=NOW + 61)
    assert auth.session_user(session, now=NOW + 62) is None
    assert auth.sign_in("alex@example.com", PASSWORD, now=NOW + 62) is None
    fresh = auth.sign_in("alex@example.com", "a different fictional password", now=NOW + 62)
    assert auth.session_user(fresh, now=NOW + 62)
    assert auth.session_user(fresh, now=NOW + 62 + auth.SESSION_SECONDS) is None


def test_login_throttling_and_deletion(mailbox):
    register(mailbox)
    for _ in range(5):
        assert auth.sign_in("alex@example.com", "wrong", now=NOW) is None
    assert auth.sign_in("alex@example.com", PASSWORD, now=NOW + 1) is None
    session = auth.sign_in("alex@example.com", PASSWORD, now=NOW + 901)
    assert session
    pm.save_profile(session["user_id"], "Alex")
    pm.delete_account(session["user_id"])
    assert auth.session_user(session, now=NOW + 902) is None
    assert auth.sign_in("alex@example.com", PASSWORD, now=NOW + 902) is None


def test_validation_and_unavailable_email(mailbox, monkeypatch):
    for invalid in ("dev:guest", "a\nBcc:other@example.com", "", "a@localhost"):
        with pytest.raises(ValueError):
            auth.request_code(invalid, now=NOW)
    code = code_for(mailbox)
    with pytest.raises(ValueError, match="12"):
        auth.set_password("alex@example.com", code, "short", now=NOW)
    monkeypatch.setattr(auth.notifications, "send_email", lambda *a, **kw: False)
    with pytest.raises(ValueError, match="couldn't send"):
        auth.request_code("blair@example.com", now=NOW)
    monkeypatch.setattr(auth.notifications, "is_configured", lambda: False)
    with pytest.raises(ValueError, match="isn't configured"):
        auth.request_code("new@example.com", now=NOW)


def test_password_ui_sign_in_onboarding_logout_and_no_google(mailbox, monkeypatch):
    import time
    register(mailbox, now=int(time.time()))
    monkeypatch.setenv("HARNESSSYNC_AUTH_MODE", "password")
    # Password mode takes precedence over stale Google settings AND dev mode.
    monkeypatch.setenv("HARNESSSYNC_DEV_MODE", "1")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=30)
    app.secrets["auth"] = {"client_id": "deleted-client"}
    app.secrets["email"] = {}
    app.run()
    assert not app.exception
    assert not app.tabs
    assert not any(b.label == "Sign in with Google" for b in app.button)
    next(w for w in app.text_input if w.label == "Email").set_value("alex@example.com")
    next(w for w in app.text_input if w.label == "Password").set_value(PASSWORD)
    next(b for b in app.button if b.label == "Sign in").click().run()
    assert not app.exception
    assert any(w.label == "Display name" for w in app.text_input)
    next(w for w in app.text_input if w.label == "Display name").set_value("Fictional Alex")
    next(b for b in app.button if b.label == "Continue").click().run()
    assert not app.exception
    assert app.tabs
    next(b for b in app.button if b.label == "Log out").click().run()
    assert not app.exception
    assert not app.tabs
    assert "password_session" not in app.session_state


def test_password_setup_ui_sends_code_and_creates_account(mailbox, monkeypatch):
    monkeypatch.setenv("HARNESSSYNC_AUTH_MODE", "password")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=30)
    app.secrets["auth"] = {}
    app.secrets["email"] = {}
    app.run()
    next(w for w in app.text_input if w.label == "Account email").set_value("alex@example.com")
    next(b for b in app.button if b.label == "Email verification code").click().run()
    assert not app.exception
    code = re.search(r"code is: ([a-f0-9]+)", mailbox[-1][0])[1]
    for label, value in (("Email to verify", "alex@example.com"), ("Verification code", code),
                         ("New password", PASSWORD), ("Confirm password", PASSWORD)):
        next(w for w in app.text_input if w.label == label).set_value(value)
    next(b for b in app.button if b.label == "Set password").click().run()
    assert not app.exception
    assert any("Password saved" in item.value for item in app.success)
    assert auth.sign_in("alex@example.com", PASSWORD)


def test_verification_mail_goes_to_user_instead_of_support_inbox(monkeypatch):
    from unittest.mock import patch
    from harnesssync import notifications
    monkeypatch.setenv("HARNESSSYNC_EMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setenv("HARNESSSYNC_EMAIL_APP_PASSWORD", "fictional")
    monkeypatch.setenv("HARNESSSYNC_EMAIL_TO_ADDRESS", "support@example.com")
    with patch("harnesssync.notifications.smtplib.SMTP_SSL") as smtp:
        assert notifications.send_email("Verification", "Fictional code", recipient="alex@example.com")
        args = smtp.return_value.__enter__.return_value.sendmail.call_args.args
        assert args[1] == ["alex@example.com"]
        assert "To: alex@example.com" in args[2]
