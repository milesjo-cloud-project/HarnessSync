"""Helpers shared by every part of the page."""

import os
import traceback
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from harnesssync.leaderboard_engine import compile_leaderboard


def _secret_section(name):
    try:
        return st.secrets.get(name, {})
    except Exception:
        return {}


def auth_configured():
    return bool(_secret_section("auth"))


def email_is_verified(claim):
    """Whether the provider vouched for the email address it handed us.

    The email *is* the account key, so an unverified one would let someone
    sign in at a provider that doesn't check addresses, claim a victim's,
    and inherit their whole log. Google always sends this claim for its own
    addresses. A provider that omits it is treated as unverified rather than
    trusted - if you add one that doesn't send the claim, this fails closed
    with a visible error instead of silently opening that door.

    Takes the raw claim because providers spell it differently: a JSON
    boolean, or the string "true".
    """
    if isinstance(claim, str):
        return claim.strip().lower() == "true"
    return claim is True


def dev_mode():
    """Local-only fallback that identifies users by a typed name instead of a
    login. Must be switched on explicitly so a deploy that's missing its auth
    config fails closed instead of silently becoming an open app."""
    return os.environ.get("HARNESSSYNC_DEV_MODE") == "1" or bool(_secret_section("app").get("dev_mode"))


def user_tz():
    """The viewer's browser timezone, so "today" means their today - not the server's (UTC)."""
    try:
        return ZoneInfo(st.context.timezone) if st.context.timezone else timezone.utc
    except Exception:
        return timezone.utc


def user_now():
    return datetime.now(user_tz())


@st.cache_data(ttl=300, show_spinner=False)
def cached_leaderboard(discipline):
    """Shared by every visitor, so the leaderboard isn't rebuilt on each click.
    Anything that can change it calls leaderboard_changed()."""
    return compile_leaderboard(discipline)


def leaderboard_changed():
    cached_leaderboard.clear()


def report_crash(error):
    """Email the developer an unhandled exception.

    Without this, a crash in production shows the visitor a traceback and
    nobody is told. Deduplicated per session so a failure that repeats on
    every rerun doesn't become a mail loop, and a no-op when email isn't
    configured. Never raises - a reporting failure must not replace the
    original error with a more confusing one.
    """
    try:
        from harnesssync import notifications

        signature = f"{type(error).__name__}: {error}"
        already_sent = st.session_state.setdefault("_reported_crashes", set())
        if signature in already_sent:
            return
        already_sent.add(signature)
        notifications.send_email(
            subject=f"HarnessSync crash: {type(error).__name__}",
            body="".join(traceback.format_exception(type(error), error, error.__traceback__)),
        )
    except Exception:
        pass


def flash(kind, message=""):
    """Queue a message to show after the next st.rerun() - anything drawn
    right before a rerun is wiped before the user can see it."""
    st.session_state.setdefault("flash", []).append((kind, message))


def show_flash():
    for kind, message in st.session_state.pop("flash", []):
        if kind == "balloons":
            st.balloons()
        else:
            st.toast(message, icon={"success": "✅", "warning": "⚠️", "info": "ℹ️"}.get(kind))
