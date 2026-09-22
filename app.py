from datetime import date, datetime

import streamlit as st
import pandas as pd
import altair as alt

from grades import (
    GRADES_BY_DISCIPLINE, SEND_STATUSES, ENVIRONMENTS, WALL_ANGLES, HOLD_TYPES, grade_rank
)
from profile_manager import (
    log_climb, get_climbs, load_all_records, log_session, get_sessions, delete_climb, update_climb,
    log_project, get_projects, update_project, delete_project, graduate_project
)
from feedback_manager import submit_feedback, load_feedback
from user_guide import render_hardware_manual_tab
from leaderboard_engine import compile_leaderboard
import notifications

st.set_page_config(page_title="HarnessSync | Climbing Intel", layout="wide")

# Custom visual card styling injection
st.markdown("""
    <style>
    .metric-container {
        background-color: #1E293B;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 10px;
        border: 1px solid #334155;
    }
    </style>
""", unsafe_allow_html=True)

# ----------------- SIDEBAR CONTROLS -----------------
st.sidebar.header("📝 Log a Climb / Session")

climber_name = st.sidebar.text_input("Climber Name", value="Guest")
discipline = st.sidebar.radio("Discipline", ["Boulder", "Rope"], horizontal=True)

with st.sidebar.form("log_climb_form", clear_on_submit=True):
    grade = st.selectbox("Grade", GRADES_BY_DISCIPLINE[discipline])
    status = st.selectbox("Send Status", SEND_STATUSES)
    environment = st.selectbox("Environment", ENVIRONMENTS)
    angle = st.selectbox("Wall Angle", WALL_ANGLES, index=1)
    hold_type = st.selectbox("Hold Type", HOLD_TYPES, index=5)
    route_name = st.text_input("Route / Problem Name (optional)")
    location = st.text_input("Location (optional)", placeholder="e.g. Movement Gym / Red River Gorge")
    climb_date = st.date_input("Date", value=date.today())
    submitted = st.form_submit_button("🧗 Log Climb", use_container_width=True)

if submitted:
    climb_date_str = climb_date.isoformat()
    if status in ["Project", "Attempt"]:
        log_project(
            climber_name, discipline, grade,
            route_name=route_name, location=location,
            environment=environment, angle=angle, hold_type=hold_type,
            attempts=1, notes="Logged from sidebar"
        )
        st.sidebar.success(f"Added {discipline} {grade} to your 🎯 Projects!")
    else:
        pr_alerts = log_climb(
            climber_name, discipline, grade, status,
            route_name=route_name, location=location,
            environment=environment, angle=angle, hold_type=hold_type,
            climb_date=climb_date_str,
        )
        st.sidebar.success(f"Logged {discipline} {grade} ({status}).")
        for alert in pr_alerts:
            st.sidebar.balloons()
            st.sidebar.success(alert)

# ----------------- SESSION TIMER -----------------
st.sidebar.markdown("---")
st.sidebar.header("⏱️ Session Timer")

if "session_start" not in st.session_state:
    st.session_state.session_start = None
    st.session_state.session_climber = None

if st.session_state.session_start is None:
    if st.sidebar.button("▶️ Start Session", use_container_width=True):
        st.session_state.session_start = datetime.now()
        st.session_state.session_climber = climber_name
        st.rerun()
else:
    elapsed_min = (datetime.now() - st.session_state.session_start).total_seconds() / 60
    start_label = st.session_state.session_start.strftime("%I:%M %p").lstrip("0")
    st.sidebar.caption(f"Started {start_label} · {elapsed_min:.0f} min so far")
    if st.sidebar.button("⏹ End Session", use_container_width=True):
        session_climber = st.session_state.session_climber
        session_ended_at = datetime.now()
        duration_min = log_session(session_climber, st.session_state.session_start, session_ended_at)
        notifications.send_email(
            subject=f"HarnessSync: {session_climber} finished a {duration_min:.0f} min session",
            body=(
                f"Climber: {session_climber}\n"
                f"Started: {st.session_state.session_start.isoformat(timespec='minutes')}\n"
                f"Ended: {session_ended_at.isoformat(timespec='minutes')}\n"
                f"Duration: {duration_min:.1f} minutes\n"
            ),
        )
        st.session_state.session_start = None
        st.session_state.session_climber = None
        st.sidebar.success(f"Session logged: {duration_min:.0f} min.")
        st.rerun()

# ----------------- MAIN PANEL HEADER -----------------
st.title("🧗 HarnessSync")
st.subheader("Climb Logging, Volume Pyramids & Project Tracking")

dashboard_tab, projects_tab, leaderboard_tab, user_feedback_tab, guide_tab = st.tabs(
    ["📊 Dashboard", "🎯 Projects", "🏆 Leaderboard", "💬 Feedback", "📖 Guide & Reference"]
)

with guide_tab:
    render_hardware_manual_tab()

with user_feedback_tab:
    st.header("💬 Feedback")
    st.caption("Bugs, ideas, or just how it's going - this goes straight to the developer.")

    with st.form("feedback_form", clear_on_submit=True):
        feedback_category = st.selectbox("Category", ["Bug", "Feature Idea", "General"])
        feedback_rating = st.slider("Overall, how's the app working for you?", 1, 5, 4)
        feedback_message = st.text_area("Details")
        feedback_submitted = st.form_submit_button("Send Feedback", use_container_width=True)

    if feedback_submitted:
        if not feedback_message.strip():
            st.warning("Add a note before sending - even a sentence helps.")
        else:
            submit_feedback(climber_name, feedback_category, feedback_rating, feedback_message)
            emailed = notifications.send_email(
                subject=f"HarnessSync feedback ({feedback_category}) from {climber_name}",
                body=f"Rating: {feedback_rating}/5\nCategory: {feedback_category}\n\n{feedback_message}",
            )
            st.success(
                "Feedback sent - thank you!"
                if emailed else
                "Feedback saved (email delivery isn't configured, so it wasn't emailed)."
            )

with projects_tab:
    st.header("🎯 Active Projects & Wishlist")
    st.caption("Routes and boulders you are working on across sessions.")

    with st.expander("➕ Add New Project"):
        with st.form("add_project_form", clear_on_submit=True):
            p_disc = st.radio("Discipline", ["Boulder", "Rope"], horizontal=True, key="p_disc")
            p_grade = st.selectbox("Grade", GRADES_BY_DISCIPLINE[p_disc], key="p_grade")
            p_route = st.text_input("Route / Problem Name", key="p_route")
            p_loc = st.text_input("Location", key="p_loc")
            p_env = st.selectbox("Environment", ENVIRONMENTS, key="p_env")
            p_angle = st.selectbox("Wall Angle", WALL_ANGLES, index=1, key="p_angle")
            p_hold = st.selectbox("Hold Type", HOLD_TYPES, index=5, key="p_hold")
            p_attempts = st.number_input("Current Attempts", min_value=1, value=1, key="p_attempts")
            p_notes = st.text_area("Beta / Notes", placeholder="e.g., heel hook on second move, small crimp at crux", key="p_notes")
            p_submit = st.form_submit_button("Save Project", use_container_width=True)

        if p_submit:
            log_project(
                climber_name, p_disc, p_grade,
                route_name=p_route, location=p_loc,
                environment=p_env, angle=p_angle, hold_type=p_hold,
                attempts=p_attempts, notes=p_notes
            )
            st.success("Project added!")
            st.rerun()

    active_projects = get_projects(climber_name)
    if not active_projects:
        st.info("No active projects right now. Use the form above or the sidebar (set status to Project) to add one!")
    else:
        for proj in active_projects:
            with st.container():
                st.markdown(f"### 🧗 {proj['discipline']} {proj['grade']} - {proj['route_name'] or 'Unnamed Project'}")
                p_col1, p_col2, p_col3, p_col4 = st.columns([2, 2, 2, 3])
                with p_col1:
                    st.write(f"**Location:** {proj['location'] or '—'}")
                    st.write(f"**Environment:** {proj.get('environment', 'Gym')}")
                with p_col2:
                    st.write(f"**Angle:** {proj.get('angle', 'Vertical')}")
                    st.write(f"**Holds:** {proj.get('hold_type', 'Mixed')}")
                with p_col3:
                    st.write(f"**Attempts:** {proj.get('attempts', 1)}")
                    st.write(f"**Added:** {proj.get('date', '—')}")
                with p_col4:
                    if proj.get('notes'):
                        st.info(f"**Notes:** {proj['notes']}")

                b_col1, b_col2, b_col3 = st.columns([2, 2, 2])
                with b_col1:
                    if st.button(f"🎉 SENT IT! (Graduate)", key=f"grad_{proj['id']}", use_container_width=True, type="primary"):
                        alerts = graduate_project(proj['id'], send_status="Redpoint")
                        st.success(f"Graduated project to send history!")
                        for a in alerts:
                            st.balloons()
                            st.success(a)
                        st.rerun()
                with b_col2:
                    if st.button(f"➕ Add Attempt (+1)", key=f"att_{proj['id']}", use_container_width=True):
                        update_project(
                            proj['id'], proj['discipline'], proj['grade'],
                            route_name=proj['route_name'], location=proj['location'],
                            environment=proj.get('environment', 'Gym'),
                            angle=proj.get('angle', 'Vertical'),
                            hold_type=proj.get('hold_type', 'Mixed'),
                            attempts=proj.get('attempts', 1) + 1,
                            notes=proj.get('notes', '')
                        )
                        st.rerun()
                with b_col3:
                    if st.button(f"🗑️ Delete", key=f"del_proj_{proj['id']}", use_container_width=True):
                        delete_project(proj['id'])
                        st.rerun()
                st.markdown("---")

with leaderboard_tab:
    st.header("🏆 Leaderboard")
    st.caption("Ranked by hardest logged grade within each discipline.")
    lb_discipline = st.radio("Discipline", ["Boulder", "Rope"], horizontal=True, key="leaderboard_discipline")
    lb_df = compile_leaderboard(lb_discipline)

    if lb_df.empty:
        st.info(f"No {lb_discipline} climbs logged yet. Log a climb to get on the board.")
    else:
        lb_df = lb_df.reset_index(drop=True)
        medals = ["🥇", "🥈", "🥉"]
        lb_df.insert(0, "Rank", [medals[i] if i < 3 else str(i + 1) for i in range(len(lb_df))])
        st.dataframe(lb_df, use_container_width=True, hide_index=True)

with dashboard_tab:
    climbs = get_climbs(climber_name)
    boulder_best = max(
        get_climbs(climber_name, "Boulder"),
        key=lambda c: grade_rank("Boulder", c["grade"]),
        default=None,
    )
    rope_best = max(
        get_climbs(climber_name, "Rope"),
        key=lambda c: grade_rank("Rope", c["grade"]),
        default=None,
    )
    today_str = date.today().isoformat()

    st.write("### 📊 Climb Overview")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric(label="Total Climbs Logged", value=len(climbs))
    with m_col2:
        st.metric(label="Best Boulder Grade", value=boulder_best["grade"] if boulder_best else "—")
    with m_col3:
        st.metric(label="Best Rope Grade", value=rope_best["grade"] if rope_best else "—")
    with m_col4:
        st.metric(label="Logged Today", value=sum(1 for c in climbs if c["date"] == today_str))

    st.markdown("---")

    # ----------------- VOLUME PYRAMID -----------------
    st.write("### 🏗️ Send Volume Pyramid & Style Breakdown")
    if not climbs:
        st.info("Log climbs to see your pyramid volume distribution!")
    else:
        pyr_disc = st.radio("Pyramid Discipline", ["Boulder", "Rope"], horizontal=True, key="pyr_disc")
        filtered_climbs = [c for c in climbs if c["discipline"] == pyr_disc and c["status"] in ["Onsight", "Flash", "Redpoint", "Sent"]]
        
        if not filtered_climbs:
            st.info(f"No completed sends logged for {pyr_disc} yet.")
        else:
            pyr_df = pd.DataFrame(filtered_climbs)
            pyr_df["Rank"] = pyr_df["grade"].apply(lambda g: grade_rank(pyr_disc, g))
            grade_counts = pyr_df.groupby(["grade", "Rank"]).size().reset_index(name="Sends")
            grade_counts = grade_counts.sort_values("Rank", ascending=True)

            pyramid_chart = alt.Chart(grade_counts).mark_bar().encode(
                x=alt.X("Sends:Q", title="Total Sends"),
                y=alt.Y("grade:N", title="Grade", sort="-x"),
                color=alt.Color("Sends:Q", scale=alt.Scale(scheme="blues")),
                tooltip=["grade", "Sends"]
            ).properties(height=300)

            st.altair_chart(pyramid_chart, use_container_width=True)

    st.markdown("---")

    # ----------------- WORKSPACE SPLIT -----------------
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.write("### 📈 Climb History")

        if not climbs:
            st.info("No climbs logged yet. Use the sidebar to log your first one.")
        else:
            history_df = pd.DataFrame(climbs)[
                ["date", "discipline", "grade", "route_name", "status", "environment", "angle", "location"]
            ]
            history_df.columns = ["Date", "Discipline", "Grade", "Route/Problem", "Status", "Env", "Angle", "Location"]
            st.dataframe(history_df, use_container_width=True, hide_index=True)

            with st.expander("🛠️ Manage / Edit / Delete Climbs"):
                climb_options = {
                    f"{c['date']} - {c['discipline']} {c['grade']} ({c['status']})"
                    + (f" | {c['route_name']}" if c['route_name'] else ""): c
                    for c in climbs
                }
                selected_label = st.selectbox("Select climb record to manage", list(climb_options.keys()))
                if selected_label:
                    target_climb = climb_options[selected_label]
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        edit_disc = st.selectbox("Discipline", ["Boulder", "Rope"], index=0 if target_climb["discipline"] == "Boulder" else 1, key="edit_disc")
                        edit_grade_list = GRADES_BY_DISCIPLINE[edit_disc]
                        curr_g_idx = edit_grade_list.index(target_climb["grade"]) if target_climb["grade"] in edit_grade_list else 0
                        edit_grade = st.selectbox("Grade", edit_grade_list, index=curr_g_idx, key="edit_grade")
                        edit_status_idx = SEND_STATUSES.index(target_climb["status"]) if target_climb["status"] in SEND_STATUSES else 0
                        edit_status = st.selectbox("Send Status", SEND_STATUSES, index=edit_status_idx, key="edit_status")
                        edit_env = st.selectbox("Environment", ENVIRONMENTS, index=ENVIRONMENTS.index(target_climb.get("environment", "Gym")) if target_climb.get("environment") in ENVIRONMENTS else 0, key="edit_env")
                    with e_col2:
                        edit_angle = st.selectbox("Wall Angle", WALL_ANGLES, index=WALL_ANGLES.index(target_climb.get("angle", "Vertical")) if target_climb.get("angle") in WALL_ANGLES else 1, key="edit_angle")
                        edit_hold = st.selectbox("Hold Type", HOLD_TYPES, index=HOLD_TYPES.index(target_climb.get("hold_type", "Mixed")) if target_climb.get("hold_type") in HOLD_TYPES else 5, key="edit_hold")
                        edit_route = st.text_input("Route / Problem Name", value=target_climb["route_name"], key="edit_route")
                        edit_loc = st.text_input("Location", value=target_climb["location"], key="edit_loc")
                        try:
                            default_d = datetime.strptime(target_climb["date"], "%Y-%m-%d").date()
                        except Exception:
                            default_d = date.today()
                        edit_date = st.date_input("Date", value=default_d, key="edit_date")

                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("💾 Save Changes", use_container_width=True, type="primary"):
                            update_climb(
                                target_climb["id"],
                                edit_disc,
                                edit_grade,
                                edit_status,
                                route_name=edit_route,
                                location=edit_loc,
                                environment=edit_env,
                                angle=edit_angle,
                                hold_type=edit_hold,
                                climb_date=edit_date.isoformat(),
                            )
                            st.success("Climb record updated!")
                            st.rerun()
                    with btn_col2:
                        if st.button("🗑️ Delete Climb", use_container_width=True):
                            delete_climb(target_climb["id"])
                            st.warning("Climb record deleted.")
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
                x=alt.X("date:O", title="Date", sort=None),
                y=alt.Y("Rank:Q", title="Difficulty Rank"),
                color=alt.Color("discipline:N", title="Discipline", scale=alt.Scale(scheme="category10")),
                tooltip=["date", "discipline", "grade", "status", "route_name", "environment"],
            ).properties(height=360).interactive()

            st.altair_chart(progression_chart, use_container_width=True)
            st.caption("💡 Higher = harder within that discipline's own scale (V-scale or YDS).")