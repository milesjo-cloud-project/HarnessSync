"""Sidebar: account menu, climb logging form and session timer."""

import streamlit as st

from harnesssync.profile_manager import (
    save_profile, display_name_taken, delete_account,
    start_session_timer, active_session_start, end_session_timer,
    DISPLAY_NAME_MAX, MAX_SESSION_MIN,
)
from harnesssync.ui.common import auth_configured, user_now, user_tz, flash, leaderboard_changed


def render_account(user_id, profile):
    display_name = profile["display_name"]
    with st.sidebar.expander(f"👤 {display_name}"):
        if auth_configured():
            st.caption(f"Signed in as {user_id}")
        with st.form("account_form"):
            new_name = st.text_input("Display name", value=display_name, max_chars=DISPLAY_NAME_MAX)
            new_show = st.checkbox("Show me on the leaderboard", value=bool(profile["show_on_leaderboard"]))
            if st.form_submit_button("Save", width="stretch"):
                if not new_name.strip():
                    st.warning("Display name can't be empty.")
                elif display_name_taken(new_name, exclude_user_id=user_id):
                    st.warning("That name is taken - try another.")
                else:
                    save_profile(user_id, new_name, new_show)
                    leaderboard_changed()
                    flash("success", "Profile updated.")
                    st.rerun()
        if auth_configured():
            st.button("Log out", on_click=st.logout, width="stretch")

        st.markdown("---")
        st.caption("Danger zone")
        confirm_delete = st.checkbox("I understand this permanently deletes all my climbs, projects and sessions")
        if st.button("Delete my account & data", disabled=not confirm_delete, width="stretch"):
            delete_account(user_id)
            leaderboard_changed()
            st.session_state.clear()
            if auth_configured():
                st.logout()
            st.rerun()


def render_session_timer(user_id, profile):
    st.sidebar.markdown("---")
    st.sidebar.header("⏱️ Session Timer")

    session_start = active_session_start(user_id, profile)
    if session_start is None:
        if st.sidebar.button("▶️ Start Session", width="stretch"):
            start_session_timer(user_id, user_now())
            st.rerun()
    else:
        session_start = session_start.astimezone(user_tz())
        elapsed_min = (user_now() - session_start).total_seconds() / 60
        start_label = session_start.strftime("%I:%M %p").lstrip("0")
        st.sidebar.caption(f"Started {start_label} · {elapsed_min:.0f} min so far")
        if elapsed_min > MAX_SESSION_MIN:
            st.sidebar.warning(
                f"This timer has run over {MAX_SESSION_MIN // 60} hours - left running by mistake? "
                f"Ending it now logs {MAX_SESSION_MIN // 60} hours, not the full stretch."
            )
        if st.sidebar.button("⏹ End Session", width="stretch"):
            duration_min = end_session_timer(user_id, user_now())
            if duration_min is not None:
                flash("success", f"Session logged: {duration_min:.0f} min.")
            st.rerun()
