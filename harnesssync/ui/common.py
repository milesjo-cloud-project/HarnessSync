"""Helpers shared by every part of the page."""

import os
import traceback
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from harnesssync.ui.language import tr

from harnesssync.leaderboard_engine import compile_leaderboard


def _secret_section(name):
    try:
        return st.secrets.get(name, {})
    except Exception:
        return {}


def auth_configured():
    return not password_auth_enabled() and bool(_secret_section("auth"))


def password_auth_enabled():
    return os.environ.get("HARNESSSYNC_AUTH_MODE", "").lower() == "password"


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


def report_crash(error, area="App"):
    """Save a sanitized incident before attempting email. Never replaces the error."""
    try:
        from harnesssync.incidents import record
        from harnesssync.support_notifications import deliver_pending
        frames = traceback.extract_tb(error.__traceback__)
        signature = (area, type(error).__name__, tuple((f.filename, f.lineno) for f in frames))
        reported = st.session_state.setdefault("_reported_crashes", {})
        if signature not in reported:
            reported[signature] = record(error, area)
        reference = reported[signature]
        try:
            deliver_pending(limit=1, event_key=f"crash:{reference}:{datetime.now(timezone.utc).date().isoformat()}")
        except Exception:
            logging.getLogger(__name__).warning("Crash notification delivery unavailable")
        return reference
    except Exception:
        logging.getLogger(__name__).warning("Incident storage unavailable")
        return None


def render_safely(area, render, *args):
    """Keep failed features isolated; Streamlit stop/rerun still propagate."""
    from harnesssync.support_config import HELP_URL
    try:
        render(*args)
    except Exception as error:
        reference = report_crash(error, area)
        st.error(tr("{area} couldn't load. Other sections are still available.", area=tr(area)))
        if reference:
            st.caption(tr("Issue recorded: {reference}. Include this reference in your report.", reference=reference))
        else:
            st.caption(tr("We couldn't save an automatic report. Please use the support link."))
        if st.button(tr("Try again"), key=f"retry_{area}"):
            st.rerun()
        st.link_button(tr("Get help"), HELP_URL)


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
