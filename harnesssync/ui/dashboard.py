"""📊 Dashboard tab: overview, pyramid, sessions, climb history and progression."""

from datetime import datetime

import streamlit as st
import pandas as pd
import altair as alt

from harnesssync.grades import (
    GRADES_BY_DISCIPLINE, SEND_STATUSES, SENT_STATUSES, ENVIRONMENTS, WALL_ANGLES, HOLD_TYPES, grade_rank,
)
from harnesssync.profile_manager import (
    get_climbs, best_send, get_sessions, delete_climb, update_climb, ROUTE_MAX, LOCATION_MAX, NOTES_MAX,
)
from harnesssync.ui.common import user_now, flash, leaderboard_changed


def render(user_id):
    climbs = get_climbs(user_id)
    sessions = get_sessions(user_id)
    # From the climbs already loaded - every click reruns this, and each query is a trip to the database
    boulder_best = best_send(climbs, "Boulder")
    rope_best = best_send(climbs, "Rope")
    today_str = user_now().date().isoformat()

    st.write("### 📊 Climb Overview")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric(label="Total Climbs Logged", value=len(climbs))
    with m_col2:
        st.metric(label="Best Boulder Send", value=boulder_best["grade"] if boulder_best else "—")
    with m_col3:
        st.metric(label="Best Rope Send", value=rope_best["grade"] if rope_best else "—")
    with m_col4:
        st.metric(label="Logged Today", value=sum(1 for c in climbs if c["date"] == today_str))

    st.markdown("---")

    # ----------------- VOLUME PYRAMID -----------------
    st.write("### 🏗️ Send Volume Pyramid & Style Breakdown")
    if not climbs:
        st.info("Log climbs to see your pyramid volume distribution!")
    else:
        pyr_disc = st.radio("Pyramid Discipline", ["Boulder", "Rope"], horizontal=True, key="pyr_disc")
        filtered_climbs = [c for c in climbs if c["discipline"] == pyr_disc and c["status"] in SENT_STATUSES]

        if not filtered_climbs:
            st.info(f"No completed sends logged for {pyr_disc} yet.")
        else:
            pyr_df = pd.DataFrame(filtered_climbs)
            pyr_df["Rank"] = pyr_df["grade"].apply(lambda g: grade_rank(pyr_disc, g))
            grade_counts = pyr_df.groupby(["grade", "Rank"]).size().reset_index(name="Sends")
            # Hardest grade on top, so a healthy base of easier sends reads as a pyramid
            hardest_first = grade_counts.sort_values("Rank", ascending=False)["grade"].tolist()

            pyramid_chart = alt.Chart(grade_counts).mark_bar().encode(
                x=alt.X("Sends:Q", title="Total Sends"),
                y=alt.Y("grade:N", title="Grade", sort=hardest_first),
                color=alt.Color("Sends:Q", scale=alt.Scale(scheme="blues")),
                tooltip=["grade", "Sends"]
            ).properties(height=300)

            st.altair_chart(pyramid_chart, width="stretch")

            style_counts = pyr_df.groupby("status").size().reset_index(name="Sends")
            style_chart = alt.Chart(style_counts).mark_bar().encode(
                x=alt.X("status:N", title="Send style", sort=SEND_STATUSES),
                y=alt.Y("Sends:Q", title="Sends"),
                color=alt.Color("status:N", title="Send style"),
                tooltip=["status", "Sends"],
            ).properties(height=220)
            st.write("#### Send style breakdown")
            st.altair_chart(style_chart, width="stretch")

    st.markdown("---")

    st.write("### ⏱️ Session History")
    if not sessions:
        st.info("Completed sessions you time will appear here.")
    else:
        sessions_df = pd.DataFrame(sessions)[["date", "started_at", "ended_at", "duration_min"]]
        sessions_df.columns = ["Date", "Started", "Ended", "Duration (min)"]
        st.dataframe(sessions_df, width="stretch", hide_index=True)
        st.download_button(
            "⬇️ Download my sessions (CSV)", sessions_df.to_csv(index=False),
            file_name="harnesssync_sessions.csv", mime="text/csv",
        )

    st.markdown("---")

    # ----------------- WORKSPACE SPLIT -----------------
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.write("### 📈 Climb History")

        if not climbs:
            st.info("No climbs logged yet. Use the sidebar to log your first one.")
        else:
            history_df = pd.DataFrame(climbs)[
                ["date", "discipline", "grade", "route_name", "status", "environment", "angle", "hold_type", "location", "notes"]
            ]
            history_df.columns = ["Date", "Discipline", "Grade", "Route/Problem", "Status", "Env", "Angle", "Holds", "Location", "Notes"]
            st.dataframe(history_df, width="stretch", hide_index=True)
            st.download_button(
                "⬇️ Download my climbs (CSV)", history_df.to_csv(index=False),
                file_name="harnesssync_climbs.csv", mime="text/csv",
            )

            with st.expander("🛠️ Manage / Edit / Delete Climbs"):
                climb_options = {c["id"]: c for c in climbs}
                selected_id = st.selectbox(
                    "Select climb record to manage", list(climb_options),
                    format_func=lambda cid: (
                        f"{climb_options[cid]['date']} - {climb_options[cid]['discipline']} "
                        f"{climb_options[cid]['grade']} ({climb_options[cid]['status']})"
                        + (f" | {climb_options[cid]['route_name']}" if climb_options[cid]["route_name"] else "")
                    ),
                )
                if selected_id is not None:
                    target_climb = climb_options[selected_id]
                    # Keys include the climb id: Streamlit keeps a keyed widget's
                    # value across reruns, so shared keys would carry climb A's
                    # values into climb B's form and Save would overwrite B with them.
                    k = target_climb["id"]
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        edit_disc = st.selectbox("Discipline", ["Boulder", "Rope"], index=0 if target_climb["discipline"] == "Boulder" else 1, key=f"edit_disc_{k}")
                        edit_grade_list = GRADES_BY_DISCIPLINE[edit_disc]
                        curr_g_idx = edit_grade_list.index(target_climb["grade"]) if target_climb["grade"] in edit_grade_list else 0
                        edit_grade = st.selectbox("Grade", edit_grade_list, index=curr_g_idx, key=f"edit_grade_{k}_{edit_disc}")
                        # Only send styles: a Project/Attempt belongs in the Projects tab, not the climb log.
                        # An older row that already has one keeps it, so saving other edits doesn't change it.
                        status_options = SENT_STATUSES + ([target_climb["status"]] if target_climb["status"] not in SENT_STATUSES else [])
                        edit_status = st.selectbox("Send Status", status_options, index=status_options.index(target_climb["status"]), key=f"edit_status_{k}")
                        edit_env = st.selectbox("Environment", ENVIRONMENTS, index=ENVIRONMENTS.index(target_climb["environment"]) if target_climb["environment"] in ENVIRONMENTS else 0, key=f"edit_env_{k}")
                    with e_col2:
                        edit_angle = st.selectbox("Wall Angle", WALL_ANGLES, index=WALL_ANGLES.index(target_climb["angle"]) if target_climb["angle"] in WALL_ANGLES else 1, key=f"edit_angle_{k}")
                        edit_hold = st.selectbox("Hold Type", HOLD_TYPES, index=HOLD_TYPES.index(target_climb["hold_type"]) if target_climb["hold_type"] in HOLD_TYPES else 5, key=f"edit_hold_{k}")
                        edit_route = st.text_input("Route / Problem Name", value=target_climb["route_name"], key=f"edit_route_{k}", max_chars=ROUTE_MAX)
                        edit_loc = st.text_input("Location", value=target_climb["location"], key=f"edit_loc_{k}", max_chars=LOCATION_MAX)
                        edit_notes = st.text_area("Notes / Beta", value=target_climb.get("notes", ""), key=f"edit_notes_{k}", max_chars=NOTES_MAX)
                        try:
                            default_d = datetime.strptime(target_climb["date"], "%Y-%m-%d").date()
                        except ValueError:
                            default_d = user_now().date()
                        today = user_now().date()
                        # Clamped: date_input raises if a stored date is already past max_value
                        edit_date = st.date_input("Date", value=min(default_d, today), max_value=today, key=f"edit_date_{k}")

                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("💾 Save Changes", width="stretch", type="primary", key=f"save_{k}"):
                            update_climb(
                                user_id, target_climb["id"], edit_disc, edit_grade, edit_status, edit_date.isoformat(),
                                route_name=edit_route, location=edit_loc,
                                environment=edit_env, angle=edit_angle, hold_type=edit_hold, notes=edit_notes,
                            )
                            leaderboard_changed()
                            flash("success", "Climb record updated!")
                            st.rerun()
                    with btn_col2:
                        if st.button("🗑️ Delete Climb", width="stretch", key=f"delete_{k}"):
                            delete_climb(user_id, target_climb["id"])
                            leaderboard_changed()
                            flash("info", "Climb record deleted.")
                            st.rerun()

    with col_right:
        st.write("### 🧗 Grade Progression")

        if not climbs:
            st.info("Log a climb in the sidebar to see your progression here.")
        else:
            prog_df = pd.DataFrame(climbs)
            prog_df["Rank"] = prog_df.apply(lambda r: grade_rank(r["discipline"], r["grade"]), axis=1)
            prog_df = prog_df.sort_values("date")

            progression_chart = alt.Chart(prog_df).mark_line(point=True, interpolate="step-after").encode(
                # Temporal, so a three-month break is wider than a rest day
                x=alt.X("date:T", title="Date"),
                y=alt.Y("Rank:Q", title="Difficulty Rank"),
                color=alt.Color("discipline:N", title="Discipline", scale=alt.Scale(scheme="category10")),
                tooltip=["date", "discipline", "grade", "status", "route_name", "environment"],
            ).properties(height=360).interactive()

            st.altair_chart(progression_chart, width="stretch")
            st.caption("💡 Higher = harder within that discipline's own scale (V-scale or YDS).")
