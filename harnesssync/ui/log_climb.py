"""Main, phone-friendly climb logging flow."""

import streamlit as st

from harnesssync.ui.language import option_label, tr

from harnesssync.grades import (
    ENVIRONMENTS,
    GRADES_BY_DISCIPLINE,
    HIGH_POINTS,
    HOLD_TYPES,
    PROJECT_STATUSES,
    SEND_STATUSES,
    WALL_ANGLES,
)
from harnesssync.profile_manager import LOCATION_MAX, ROUTE_MAX, log_climb, log_project, get_logging_defaults
from harnesssync.ui import gym_reports
from harnesssync.ui.common import flash, leaderboard_changed, render_safely, user_now


def render(user_id):
    st.header(tr("Log a climb"))
    st.caption(tr("A quick record is enough. Add route details if you want them."))
    gym = None
    def arrival():
        nonlocal gym
        gym = gym_reports.render_arrival(user_id)
    render_safely("Gym", arrival)

    latest = get_logging_defaults(user_id)
    if st.session_state.get("_quick_log_account") != user_id:
        for key in list(st.session_state):
            if key.startswith("quick_"):
                del st.session_state[key]
        st.session_state["_quick_log_account"] = user_id
    if st.session_state.pop("_quick_log_saved", False):
        for key in ("quick_route", "quick_status", "quick_date", "quick_high_point"):
            st.session_state.pop(key, None)
    # Defaults live in Session State only. Passing index=/value= as well makes
    # Streamlit log a "default value but also set via Session State" warning.
    st.session_state.setdefault("quick_status", "Sent")
    st.session_state.setdefault("quick_date", user_now().date())
    discipline = st.segmented_control(
        tr("Discipline"), ["Boulder", "Rope"], default=latest.get("discipline", "Boulder"), key="quick_log_discipline",
        format_func=option_label(),
    )
    if discipline is None:
        st.info(tr("Choose Boulder or Rope to log a climb."))
        return
    defaults = get_logging_defaults(user_id, discipline)
    def previous_index(options, field, fallback=0):
        value = defaults.get(field)
        return options.index(value) if value in options else fallback

    # Outside the form so the high-point buttons can appear as soon as a try
    # is picked. Big tap targets: this is used standing at the wall.
    status = st.pills(
        tr("What happened?"), SEND_STATUSES, format_func=option_label(), key="quick_status",
        help=tr("Choose Project or Attempt if you haven't sent it yet."),
    )
    if status is None:
        st.info(tr("Tap what happened to log a climb."))
        return

    with st.form(f"quick_log_climb_form_{user_id}"):
        grades = GRADES_BY_DISCIPLINE[discipline]
        grade = st.pills(tr("Grade"), grades, default=grades[previous_index(grades, "grade")],
                         key=f"quick_grade_{discipline}")
        high_point = None
        if status in PROJECT_STATUSES:
            high_point = st.pills(tr("How high did you get?"), HIGH_POINTS, format_func=option_label(),
                                  key="quick_high_point")
        with st.expander(tr("More details (optional)")):
            route_name = st.text_input(tr("Route or problem name (optional)"), max_chars=ROUTE_MAX, key="quick_route")
            location = st.text_input(tr("Gym or crag (optional)"),
                                     value=(gym["name"] if gym else "") or defaults.get("location", ""),
                                     max_chars=LOCATION_MAX)
            environment = st.selectbox(tr("Where did you climb?"), ENVIRONMENTS,
                                       index=ENVIRONMENTS.index("Gym") if gym else previous_index(ENVIRONMENTS, "environment"),
                                       format_func=option_label())
            climb_date = st.date_input(tr("Date"), max_value=user_now().date(), key="quick_date")
            angle = st.selectbox(tr("Wall angle"), WALL_ANGLES, index=1, format_func=option_label())
            hold_type = st.selectbox(tr("Hold type"), HOLD_TYPES, index=5, format_func=option_label())

        submitted = st.form_submit_button(tr("Save climb"), type="primary", width="stretch")

    if not submitted:
        return
    if grade is None:
        st.warning(tr("Tap a grade first."))
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
            high_point=high_point or "",
        )
        flash(
            "success",
            tr("Added an attempt to your {discipline} {grade} project!", discipline=tr(discipline), grade=grade)
            if result == "bumped"
            else tr("Added {discipline} {grade} to Projects.", discipline=tr(discipline), grade=grade),
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
        flash("success", tr("Logged {discipline} {grade} ({status}).", discipline=tr(discipline), grade=grade, status=tr(status)))
        for alert in alerts:
            flash("balloons")
            flash("success", tr("🏆 New {discipline} personal best: {grade}!", discipline=tr(discipline), grade=grade))
    st.session_state["_quick_log_saved"] = True
    st.rerun()
