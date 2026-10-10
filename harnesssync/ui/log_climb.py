"""Main, phone-friendly climb logging flow."""

import streamlit as st

from harnesssync.grades import (
    ENVIRONMENTS,
    GRADES_BY_DISCIPLINE,
    HOLD_TYPES,
    PROJECT_STATUSES,
    SEND_STATUSES,
    WALL_ANGLES,
)
from harnesssync.profile_manager import LOCATION_MAX, ROUTE_MAX, log_climb, log_project
from harnesssync.ui.common import flash, leaderboard_changed, user_now


def render(user_id):
    st.header("Log a climb")
    st.caption("A quick record is enough. Add route details if you want them.")

    discipline = st.segmented_control(
        "Discipline", ["Boulder", "Rope"], default="Boulder", key="quick_log_discipline"
    )
    with st.form("quick_log_climb_form", clear_on_submit=True):
        grade = st.selectbox("Grade", GRADES_BY_DISCIPLINE[discipline])
        status = st.selectbox(
            "What happened?",
            SEND_STATUSES,
            index=SEND_STATUSES.index("Sent"),
            help="Choose Project or Attempt if you haven't sent it yet.",
        )
        environment = st.selectbox("Where did you climb?", ENVIRONMENTS, index=0)
        route_name = st.text_input("Route or problem name (optional)", max_chars=ROUTE_MAX)
        location = st.text_input("Gym or crag (optional)", placeholder="e.g. Movement RiNo", max_chars=LOCATION_MAX)
        climb_date = st.date_input("Date", value=user_now().date(), max_value=user_now().date())

        with st.expander("More details (optional)"):
            angle = st.selectbox("Wall angle", WALL_ANGLES, index=1)
            hold_type = st.selectbox("Hold type", HOLD_TYPES, index=5)

        submitted = st.form_submit_button("Save climb", type="primary", width="stretch")

    if not submitted:
        return

    if status in PROJECT_STATUSES:
        result = log_project(
            user_id,
            discipline,
            grade,
            climb_date.isoformat(),
            route_name=route_name,
            location=location,
            environment=environment,
            angle=angle,
            hold_type=hold_type,
        )
        flash(
            "success",
            f"Added an attempt to your {discipline} {grade} project!"
            if result == "bumped"
            else f"Added {discipline} {grade} to Projects.",
        )
    else:
        alerts = log_climb(
            user_id,
            discipline,
            grade,
            status,
            climb_date.isoformat(),
            route_name=route_name,
            location=location,
            environment=environment,
            angle=angle,
            hold_type=hold_type,
        )
        leaderboard_changed()
        flash("success", f"Logged {discipline} {grade} ({status}).")
        for alert in alerts:
            flash("balloons")
            flash("success", alert)
    st.rerun()
