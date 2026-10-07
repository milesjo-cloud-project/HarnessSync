"""🎯 Projects tab: routes being worked across sessions."""

from datetime import datetime

import streamlit as st
import pandas as pd

from harnesssync.grades import GRADES_BY_DISCIPLINE, ENVIRONMENTS, WALL_ANGLES, HOLD_TYPES, SENT_STATUSES
from harnesssync.profile_manager import (
    log_project, get_projects, update_project, add_project_attempt, delete_project, graduate_project,
    ROUTE_MAX, LOCATION_MAX, NOTES_MAX,
)
from harnesssync.ui.common import user_now, flash, leaderboard_changed


def render(user_id):
    st.header("🎯 Active Projects & Wishlist")
    st.caption("Routes and boulders you are working on across sessions.")

    with st.expander("➕ Add New Project"):
        # Outside the form: the grade list depends on it, and widgets inside a
        # form don't rerun the script until submit.
        p_disc = st.radio("New project discipline", ["Boulder", "Rope"], horizontal=True, key="p_disc")
        with st.form("add_project_form", clear_on_submit=True):
            p_grade = st.selectbox("Grade", GRADES_BY_DISCIPLINE[p_disc], key="p_grade")
            p_route = st.text_input("Route / Problem Name", key="p_route", max_chars=ROUTE_MAX)
            p_loc = st.text_input("Location", key="p_loc", max_chars=LOCATION_MAX)
            p_env = st.selectbox("Environment", ENVIRONMENTS, key="p_env")
            p_angle = st.selectbox("Wall Angle", WALL_ANGLES, index=1, key="p_angle")
            p_hold = st.selectbox("Hold Type", HOLD_TYPES, index=5, key="p_hold")
            p_attempts = st.number_input("Current Attempts", min_value=1, max_value=10000, value=1, key="p_attempts")
            p_notes = st.text_area("Beta / Notes", placeholder="e.g., heel hook on second move, small crimp at crux",
                                   key="p_notes", max_chars=NOTES_MAX)
            p_submit = st.form_submit_button("Save Project", width="stretch")

        if p_submit:
            log_project(
                user_id, p_disc, p_grade, user_now().date().isoformat(),
                route_name=p_route, location=p_loc,
                environment=p_env, angle=p_angle, hold_type=p_hold,
                attempts=int(p_attempts), notes=p_notes
            )
            flash("success", "Project saved!")
            st.rerun()

    active_projects = get_projects(user_id)
    if not active_projects:
        st.info("No active projects right now. Use the form above or the sidebar (set status to Project) to add one!")
    else:
        projects_df = pd.DataFrame(active_projects)[
            ["date", "discipline", "grade", "route_name", "location", "environment", "angle", "hold_type", "attempts", "notes"]
        ]
        projects_df.columns = ["Date added", "Discipline", "Grade", "Route/Problem", "Location", "Environment", "Angle", "Holds", "Attempts", "Notes"]
        st.download_button(
            "⬇️ Download my projects (CSV)", projects_df.to_csv(index=False),
            file_name="harnesssync_projects.csv", mime="text/csv",
        )
        for proj in active_projects:
            with st.container():
                st.markdown(f"### 🧗 {proj['discipline']} {proj['grade']} - {proj['route_name'] or 'Unnamed Project'}")
                p_col1, p_col2, p_col3, p_col4 = st.columns([2, 2, 2, 3])
                with p_col1:
                    st.write(f"**Location:** {proj['location'] or '—'}")
                    st.write(f"**Environment:** {proj['environment']}")
                with p_col2:
                    st.write(f"**Angle:** {proj['angle']}")
                    st.write(f"**Holds:** {proj['hold_type']}")
                with p_col3:
                    st.write(f"**Attempts:** {proj['attempts']}")
                    st.write(f"**Added:** {proj['date']}")
                with p_col4:
                    if proj["notes"]:
                        st.info(f"**Notes:** {proj['notes']}")

                with st.expander("✏️ Edit project details"):
                    e_disc = st.selectbox(
                        "Discipline", ["Boulder", "Rope"],
                        index=0 if proj["discipline"] == "Boulder" else 1,
                        key=f"project_disc_{proj['id']}",
                    )
                    e_grades = GRADES_BY_DISCIPLINE[e_disc]
                    e_grade = st.selectbox(
                        "Grade", e_grades,
                        index=e_grades.index(proj["grade"]) if proj["grade"] in e_grades else 0,
                        key=f"project_grade_{proj['id']}_{e_disc}",
                    )
                    with st.form(f"edit_project_form_{proj['id']}"):
                        e_route = st.text_input("Route / Problem Name", value=proj["route_name"], max_chars=ROUTE_MAX)
                        e_location = st.text_input("Location", value=proj["location"], max_chars=LOCATION_MAX)
                        e_env = st.selectbox("Environment", ENVIRONMENTS, index=ENVIRONMENTS.index(proj["environment"]) if proj["environment"] in ENVIRONMENTS else 0)
                        e_angle = st.selectbox("Wall Angle", WALL_ANGLES, index=WALL_ANGLES.index(proj["angle"]) if proj["angle"] in WALL_ANGLES else 1)
                        e_hold = st.selectbox("Hold Type", HOLD_TYPES, index=HOLD_TYPES.index(proj["hold_type"]) if proj["hold_type"] in HOLD_TYPES else 5)
                        try:
                            e_date_default = datetime.strptime(proj["date"], "%Y-%m-%d").date()
                        except ValueError:
                            e_date_default = user_now().date()
                        today = user_now().date()
                        e_date = st.date_input("Date added", value=min(e_date_default, today), max_value=today)
                        e_attempts = st.number_input("Attempts", min_value=1, max_value=10000, value=int(proj["attempts"]))
                        e_notes = st.text_area("Beta / Notes", value=proj["notes"], max_chars=NOTES_MAX)
                        if st.form_submit_button("Save project details", width="stretch"):
                            update_project(
                                user_id, proj["id"], e_disc, e_grade, e_date.isoformat(),
                                route_name=e_route, location=e_location, environment=e_env,
                                angle=e_angle, hold_type=e_hold, attempts=int(e_attempts), notes=e_notes,
                            )
                            flash("success", "Project updated.")
                            st.rerun()

                b_col1, b_col2, b_col3 = st.columns([2, 2, 2])
                with b_col1:
                    # The send style is the interesting part of a send, and it's
                    # known exactly at this moment - don't assume Redpoint.
                    send_status = st.selectbox(
                        "Send style", SENT_STATUSES,
                        index=SENT_STATUSES.index("Redpoint"),
                        key=f"grad_style_{proj['id']}",
                    )
                    if st.button("🎉 SENT IT! (Graduate)", key=f"grad_{proj['id']}", width="stretch", type="primary"):
                        alerts = graduate_project(user_id, proj["id"], user_now().date().isoformat(), send_status=send_status)
                        leaderboard_changed()
                        flash("success", "Graduated project to send history!")
                        for a in alerts:
                            flash("balloons")
                            flash("success", a)
                        st.rerun()
                with b_col2:
                    if st.button("➕ Add Attempt (+1)", key=f"att_{proj['id']}", width="stretch"):
                        add_project_attempt(user_id, proj["id"])
                        st.rerun()
                with b_col3:
                    if st.button("🗑️ Delete", key=f"del_proj_{proj['id']}", width="stretch"):
                        delete_project(user_id, proj["id"])
                        flash("info", "Project deleted.")
                        st.rerun()
                st.markdown("---")
