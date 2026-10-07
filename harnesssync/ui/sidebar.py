"""Sidebar: account menu, climb logging form and session timer."""

import streamlit as st

from harnesssync.grades import GRADES_BY_DISCIPLINE, SEND_STATUSES, PROJECT_STATUSES, ENVIRONMENTS, WALL_ANGLES, HOLD_TYPES
from harnesssync.profile_manager import (
    save_profile, display_name_taken, delete_account, log_climb, log_project,
    start_session_timer, active_session_start, end_session_timer,
    DISPLAY_NAME_MAX, ROUTE_MAX, LOCATION_MAX, MAX_SESSION_MIN,
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


def render_log_form(user_id):
    st.sidebar.header("📝 Log a Climb / Session")
    # Several "Discipline" pickers render on one page. Distinct labels so a
    # screen reader doesn't announce four identical controls.
    discipline = st.sidebar.radio("Discipline to log", ["Boulder", "Rope"], horizontal=True)

    with st.sidebar.form("log_climb_form", clear_on_submit=True):
        grade = st.selectbox("Grade", GRADES_BY_DISCIPLINE[discipline])
        status = st.selectbox("Send Status", SEND_STATUSES)
        environment = st.selectbox("Environment", ENVIRONMENTS)
        angle = st.selectbox("Wall Angle", WALL_ANGLES, index=1)
        hold_type = st.selectbox("Hold Type", HOLD_TYPES, index=5)
        route_name = st.text_input("Route / Problem Name (optional)", max_chars=ROUTE_MAX)
        location = st.text_input("Location (optional)", placeholder="e.g. Movement Gym / Red River Gorge", max_chars=LOCATION_MAX)
        climb_date = st.date_input("Date", value=user_now().date(), max_value=user_now().date())
        submitted = st.form_submit_button("🧗 Log Climb", width="stretch")

    if submitted:
        if status in PROJECT_STATUSES:
            result = log_project(
                user_id, discipline, grade, climb_date.isoformat(),
                route_name=route_name, location=location,
                environment=environment, angle=angle, hold_type=hold_type,
            )
            flash("success", f"Added an attempt to your {discipline} {grade} project!"
                  if result == "bumped" else f"Added {discipline} {grade} to your 🎯 Projects!")
        else:
            pr_alerts = log_climb(
                user_id, discipline, grade, status, climb_date.isoformat(),
                route_name=route_name, location=location,
                environment=environment, angle=angle, hold_type=hold_type,
            )
            leaderboard_changed()
            flash("success", f"Logged {discipline} {grade} ({status}).")
            for alert in pr_alerts:
                flash("balloons")
                flash("success", alert)
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
