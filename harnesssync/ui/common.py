"""Helpers shared by every part of the page."""

import os
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
