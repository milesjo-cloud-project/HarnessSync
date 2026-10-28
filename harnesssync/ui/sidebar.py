"""Sidebar: account menu, climb logging form and session timer."""

import streamlit as st

from harnesssync.ui.language import tr

from harnesssync.profile_manager import (
    save_profile, display_name_taken, delete_account,
    start_session_timer, active_session_start, end_session_timer,
    DISPLAY_NAME_MAX, MAX_SESSION_MIN,
)
from harnesssync.ui.common import auth_configured, user_now, user_tz, flash, leaderboard_changed, password_auth_enabled


def render_account(user_id, profile):
    display_name = profile["display_name"]
    with st.sidebar.expander(f"👤 {display_name}"):
        if auth_configured():
            st.caption(tr("Signed in as {user}", user=user_id))
        with st.form("account_form"):
            new_name = st.text_input(tr("Display name"), value=display_name, max_chars=DISPLAY_NAME_MAX)
            new_show = st.checkbox(tr("Show me on the leaderboard"), value=bool(profile["show_on_leaderboard"]))
            if st.form_submit_button(tr("Save"), width="stretch"):
                if not new_name.strip():
                    st.warning(tr("Display name can't be empty."))
                elif display_name_taken(new_name, exclude_user_id=user_id):
                    st.warning(tr("That name is taken - try another."))
                else:
                    save_profile(user_id, new_name, new_show)
                    leaderboard_changed()
                    flash("success", tr("Profile updated."))
                    st.rerun()
        if auth_configured():
            st.button(tr("Log out"), on_click=st.logout, width="stretch")
        elif password_auth_enabled():
            st.caption(tr("Signed in as {user}", user=user_id))
            if st.button(tr("Log out"), width="stretch"):
                st.session_state.clear()
                st.rerun()

        st.markdown("---")
        st.caption(tr("Danger zone"))
        confirm_delete = st.checkbox(tr("I understand this permanently deletes all my climbs, projects and sessions"))
        if st.button(tr("Delete my account & data"), disabled=not confirm_delete, width="stretch"):
            delete_account(user_id)
            leaderboard_changed()
            st.session_state.clear()
            if auth_configured():
                st.logout()
            st.rerun()


def render_session_timer(user_id, profile):
    st.sidebar.markdown("---")
    st.sidebar.header(tr("⏱️ Session Timer"))

    session_start = active_session_start(user_id, profile)
    if session_start is None:
        if st.sidebar.button(tr("▶️ Start Session"), width="stretch"):
            start_session_timer(user_id, user_now())
            st.rerun()
    else:
        session_start = session_start.astimezone(user_tz())
        elapsed_min = (user_now() - session_start).total_seconds() / 60
        start_label = session_start.strftime("%I:%M %p").lstrip("0")
        st.sidebar.caption(tr("Started {time} · {minutes} min so far", time=start_label, minutes=f"{elapsed_min:.0f}"))
        if elapsed_min > MAX_SESSION_MIN:
            st.sidebar.warning(
                tr("This timer has run over {hours} hours - left running by mistake? "
                   "Ending it now logs {hours} hours, not the full stretch.", hours=MAX_SESSION_MIN // 60)
            )
        if st.sidebar.button(tr("⏹ End Session"), width="stretch"):
            duration_min = end_session_timer(user_id, user_now())
            if duration_min is not None:
                flash("success", tr("Session logged: {minutes} min.", minutes=f"{duration_min:.0f}"))
                st.session_state["main_tabs"] = tr("📊 Progress")
                st.session_state["progress_view"] = "Session recaps"
            st.rerun()
