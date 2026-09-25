import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st
import pandas as pd
import altair as alt

from grades import (
    GRADES_BY_DISCIPLINE, SEND_STATUSES, SENT_STATUSES, PROJECT_STATUSES,
    ENVIRONMENTS, WALL_ANGLES, HOLD_TYPES, grade_rank
)
from profile_manager import (
    get_profile, save_profile, display_name_taken, delete_account,
    log_climb, get_climbs, best_climb, log_session, delete_climb, update_climb,
    log_project, get_projects, add_project_attempt, delete_project, graduate_project,
    DISPLAY_NAME_MAX, ROUTE_MAX, LOCATION_MAX, NOTES_MAX,
)
from feedback_manager import submit_feedback, feedback_block_reason, MESSAGE_MAX
from user_guide import render_hardware_manual_tab
from leaderboard_engine import compile_leaderboard
import notifications

st.set_page_config(page_title="HarnessSync | Climbing Intel", layout="wide")


# ----------------- HELPERS -----------------
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


def resolve_user():
    """Returns (user_id, suggested_display_name) for whoever is using the app,
    or stops the script to show a sign-in screen."""
    if auth_configured():
        if not st.user.is_logged_in:
            st.title("🧗 HarnessSync")
            st.subheader("Climb Logging, Volume Pyramids & Project Tracking")
            st.write(
                "Log your sends, track projects across sessions, and see your grade pyramid "
                "and progression over time. Sign in to get started - your log is private to you."
            )
            st.button("Sign in with Google", on_click=st.login, type="primary")
            st.stop()
        user_id = st.user.get("email") or st.user.get("sub")
        return user_id, st.user.get("given_name") or st.user.get("name") or ""

    if dev_mode():
        st.sidebar.warning("Dev mode: no login - anyone can use any name. Never deploy like this.")
        name = st.sidebar.text_input("Climber Name", value="Guest", max_chars=DISPLAY_NAME_MAX).strip()
        if not name:
            st.info("Enter a climber name in the sidebar to get started.")
            st.stop()
        return f"dev:{name.lower()}", name

    st.error(
        "Sign-in isn't configured. Add an `[auth]` section to `.streamlit/secrets.toml` "
        "(see DEPLOYMENT.md), or set `HARNESSSYNC_DEV_MODE=1` to run locally without login."
    )
    st.stop()


def render_onboarding(user_id, suggested_name):
    st.title("🧗 Welcome to HarnessSync")
    st.write("Pick the name other climbers will see on the leaderboard. You can change it later.")
    with st.form("onboarding_form"):
        name = st.text_input("Display name", value=suggested_name[:DISPLAY_NAME_MAX], max_chars=DISPLAY_NAME_MAX)
        show = st.checkbox("Show me on the public leaderboard", value=True)
        if st.form_submit_button("Continue", type="primary"):
            if not name.strip():
                st.warning("Display name can't be empty.")
            elif display_name_taken(name, exclude_user_id=user_id):
                st.warning("That name is taken - try another.")
            else:
                save_profile(user_id, name, show)
                st.rerun()
    st.stop()


# ----------------- IDENTITY -----------------
user_id, suggested_name = resolve_user()
profile = get_profile(user_id)
if profile is None:
    if dev_mode() and not auth_configured():
        save_profile(user_id, suggested_name)
        profile = get_profile(user_id)
    else:
        render_onboarding(user_id, suggested_name)
display_name = profile["display_name"]

show_flash()

# ----------------- SIDEBAR: ACCOUNT -----------------
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
                flash("success", "Profile updated.")
                st.rerun()
    if auth_configured():
        st.button("Log out", on_click=st.logout, width="stretch")

    st.markdown("---")
    st.caption("Danger zone")
    confirm_delete = st.checkbox("I understand this permanently deletes all my climbs, projects and sessions")
    if st.button("Delete my account & data", disabled=not confirm_delete, width="stretch"):
        delete_account(user_id)
        st.session_state.clear()
        if auth_configured():
            st.logout()
        st.rerun()

# ----------------- SIDEBAR: LOG A CLIMB -----------------
st.sidebar.header("📝 Log a Climb / Session")
discipline = st.sidebar.radio("Discipline", ["Boulder", "Rope"], horizontal=True)

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
        flash("success", f"Logged {discipline} {grade} ({status}).")
        for alert in pr_alerts:
            flash("balloons")
            flash("success", alert)
    st.rerun()

# ----------------- SESSION TIMER -----------------
st.sidebar.markdown("---")
st.sidebar.header("⏱️ Session Timer")

if st.session_state.get("session_start") is None:
    if st.sidebar.button("▶️ Start Session", width="stretch"):
        st.session_state.session_start = user_now()
        st.session_state.session_user = user_id
        st.rerun()
else:
    session_start = st.session_state.session_start
    elapsed_min = (user_now() - session_start).total_seconds() / 60
    start_label = session_start.strftime("%I:%M %p").lstrip("0")
    st.sidebar.caption(f"Started {start_label} · {elapsed_min:.0f} min so far")
    if st.sidebar.button("⏹ End Session", width="stretch"):
        duration_min = log_session(st.session_state.session_user, session_start, user_now())
        st.session_state.session_start = None
        st.session_state.session_user = None
        flash("success", f"Session logged: {duration_min:.0f} min.")
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
        feedback_message = st.text_area("Details", max_chars=MESSAGE_MAX)
        feedback_submitted = st.form_submit_button("Send Feedback", width="stretch")

    if feedback_submitted:
        blocked = feedback_block_reason(user_id)
        if not feedback_message.strip():
            st.warning("Add a note before sending - even a sentence helps.")
        elif blocked:
            st.warning(blocked)
        else:
            submit_feedback(user_id, display_name, feedback_category, feedback_rating, feedback_message)
            emailed = notifications.send_email(
                subject=f"HarnessSync feedback ({feedback_category}) from {display_name}",
                body=(
                    f"From: {display_name} ({user_id})\n"
                    f"Rating: {feedback_rating}/5\nCategory: {feedback_category}\n\n{feedback_message}"
                ),
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
        # Outside the form: the grade list depends on it, and widgets inside a
        # form don't rerun the script until submit.
        p_disc = st.radio("Discipline", ["Boulder", "Rope"], horizontal=True, key="p_disc")
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

                b_col1, b_col2, b_col3 = st.columns([2, 2, 2])
                with b_col1:
                    if st.button("🎉 SENT IT! (Graduate)", key=f"grad_{proj['id']}", width="stretch", type="primary"):
                        alerts = graduate_project(user_id, proj["id"], user_now().date().isoformat(), send_status="Redpoint")
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

with leaderboard_tab:
    st.header("🏆 Leaderboard")
    st.caption("Ranked by hardest send (Onsight, Flash, Redpoint or Sent) within each discipline. "
               "You can hide yourself from the leaderboard in the 👤 account menu.")
    lb_discipline = st.radio("Discipline", ["Boulder", "Rope"], horizontal=True, key="leaderboard_discipline")
    lb_df = compile_leaderboard(lb_discipline)

    if lb_df.empty:
        st.info(f"No {lb_discipline} sends logged yet. Log one to get on the board.")
    else:
        lb_df = lb_df.reset_index(drop=True)
        medals = ["🥇", "🥈", "🥉"]
        lb_df.insert(0, "Rank", [medals[i] if i < 3 else str(i + 1) for i in range(len(lb_df))])
        st.dataframe(lb_df, width="stretch", hide_index=True)

with dashboard_tab:
    climbs = get_climbs(user_id)
    boulder_best = best_climb(user_id, "Boulder")
    rope_best = best_climb(user_id, "Rope")
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
            grade_counts = grade_counts.sort_values("Rank", ascending=True)

            pyramid_chart = alt.Chart(grade_counts).mark_bar().encode(
                x=alt.X("Sends:Q", title="Total Sends"),
                y=alt.Y("grade:N", title="Grade", sort="-x"),
                color=alt.Color("Sends:Q", scale=alt.Scale(scheme="blues")),
                tooltip=["grade", "Sends"]
            ).properties(height=300)

            st.altair_chart(pyramid_chart, width="stretch")

    st.markdown("---")

    # ----------------- WORKSPACE SPLIT -----------------
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.write("### 📈 Climb History")

        if not climbs:
            st.info("No climbs logged yet. Use the sidebar to log your first one.")
        else:
            history_df = pd.DataFrame(climbs)[
                ["date", "discipline", "grade", "route_name", "status", "environment", "angle", "hold_type", "location"]
            ]
            history_df.columns = ["Date", "Discipline", "Grade", "Route/Problem", "Status", "Env", "Angle", "Holds", "Location"]
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
                        edit_status_idx = SEND_STATUSES.index(target_climb["status"]) if target_climb["status"] in SEND_STATUSES else 0
                        edit_status = st.selectbox("Send Status", SEND_STATUSES, index=edit_status_idx, key=f"edit_status_{k}")
                        edit_env = st.selectbox("Environment", ENVIRONMENTS, index=ENVIRONMENTS.index(target_climb["environment"]) if target_climb["environment"] in ENVIRONMENTS else 0, key=f"edit_env_{k}")
                    with e_col2:
                        edit_angle = st.selectbox("Wall Angle", WALL_ANGLES, index=WALL_ANGLES.index(target_climb["angle"]) if target_climb["angle"] in WALL_ANGLES else 1, key=f"edit_angle_{k}")
                        edit_hold = st.selectbox("Hold Type", HOLD_TYPES, index=HOLD_TYPES.index(target_climb["hold_type"]) if target_climb["hold_type"] in HOLD_TYPES else 5, key=f"edit_hold_{k}")
                        edit_route = st.text_input("Route / Problem Name", value=target_climb["route_name"], key=f"edit_route_{k}", max_chars=ROUTE_MAX)
                        edit_loc = st.text_input("Location", value=target_climb["location"], key=f"edit_loc_{k}", max_chars=LOCATION_MAX)
                        try:
                            default_d = datetime.strptime(target_climb["date"], "%Y-%m-%d").date()
                        except ValueError:
                            default_d = user_now().date()
                        edit_date = st.date_input("Date", value=default_d, key=f"edit_date_{k}")

                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("💾 Save Changes", width="stretch", type="primary", key=f"save_{k}"):
                            update_climb(
                                user_id, target_climb["id"], edit_disc, edit_grade, edit_status, edit_date.isoformat(),
                                route_name=edit_route, location=edit_loc,
                                environment=edit_env, angle=edit_angle, hold_type=edit_hold,
                            )
                            flash("success", "Climb record updated!")
                            st.rerun()
                    with btn_col2:
                        if st.button("🗑️ Delete Climb", width="stretch", key=f"delete_{k}"):
                            delete_climb(user_id, target_climb["id"])
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
                x=alt.X("date:O", title="Date", sort=None),
                y=alt.Y("Rank:Q", title="Difficulty Rank"),
                color=alt.Color("discipline:N", title="Discipline", scale=alt.Scale(scheme="category10")),
                tooltip=["date", "discipline", "grade", "status", "route_name", "environment"],
            ).properties(height=360).interactive()

            st.altair_chart(progression_chart, width="stretch")
            st.caption("💡 Higher = harder within that discipline's own scale (V-scale or YDS).")
