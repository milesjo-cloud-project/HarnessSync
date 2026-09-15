from datetime import date, datetime

import streamlit as st
import pandas as pd
import altair as alt

from grades import GRADES_BY_DISCIPLINE, SEND_STATUSES, grade_rank
from profile_manager import log_climb, get_climbs, load_all_records, log_session, get_sessions
from feedback_manager import submit_feedback, load_feedback
from user_guide import render_hardware_manual_tab
from leaderboard_engine import compile_leaderboard
import ai_coach
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
st.sidebar.header("📝 Log a Climb")

climber_name = st.sidebar.text_input("Climber Name", value="Guest")
# Outside the form (not the grade/status fields below) so switching disciplines
# reruns immediately and the grade dropdown always matches - inside a form,
# widgets don't rerun until submit, so the grade list would stay stale until
# the climb was already logged.
discipline = st.sidebar.radio("Discipline", ["Boulder", "Rope"], horizontal=True)

with st.sidebar.form("log_climb_form", clear_on_submit=True):
    grade = st.selectbox("Grade", GRADES_BY_DISCIPLINE[discipline])
    status = st.selectbox("Send Status", SEND_STATUSES)
    route_name = st.text_input("Route / Problem Name (optional)")
    location = st.text_input("Location (optional)", placeholder="e.g. The Rock Gym")
    climb_date = st.date_input("Date", value=date.today())
    submitted = st.form_submit_button("🧗 Log Climb", use_container_width=True)

if submitted:
    climb_date_str = climb_date.isoformat()
    pr_alerts = log_climb(
        climber_name, discipline, grade, status,
        route_name=route_name, location=location, climb_date=climb_date_str,
    )
    st.sidebar.success(f"Logged {discipline} {grade} ({status}).")
    for alert in pr_alerts:
        st.sidebar.balloons()
        st.sidebar.success(alert)

    if ai_coach.is_configured():
        entry = {
            "date": climb_date_str, "discipline": discipline, "grade": grade,
            "status": status, "route_name": route_name, "location": location,
        }
        try:
            st.session_state.last_coach_feedback = ai_coach.analyze_session(
                climber_name, discipline, entry, get_climbs(climber_name, discipline)[:10],
            )
        except Exception as exc:
            st.session_state.last_coach_feedback = f"⚠️ Coach feedback failed: {exc}"

# ----------------- SESSION TIMER -----------------
# Tracks a whole gym/crag visit (not an individual climb) - "Start" when you
# walk in, "End" when you're leaving. Kept in session_state, so it's scoped
# to this one browser tab/visitor, same as every other widget here.
st.sidebar.markdown("---")
st.sidebar.header("⏱️ Session Timer")

if "session_start" not in st.session_state:
    st.session_state.session_start = None
    st.session_state.session_climber = None

if st.session_state.session_start is None:
    if st.sidebar.button("▶️ Start Session", use_container_width=True):
        st.session_state.session_start = datetime.now()
        # Snapshotted here, not read again at End Session - the Climber Name
        # box above is a live widget, so if it were re-read at End time,
        # editing it mid-visit (e.g. handing the phone to a friend) would
        # silently reattribute the whole session to the new name.
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
st.subheader("Climb Logging, Grade Progression & Leaderboards")

dashboard_tab, leaderboard_tab, coach_tab, user_feedback_tab, admin_tab, guide_tab = st.tabs(
    ["📊 Dashboard", "🏆 Leaderboard", "🤖 AI Coach", "💬 Feedback", "🔐 Admin", "📖 Guide"]
)

with guide_tab:
    render_hardware_manual_tab()

with coach_tab:
    st.header("🤖 AI Coach")

    if not ai_coach.is_configured():
        st.warning(
            "AI Coach isn't configured yet. Add your Anthropic API key to "
            "`.streamlit/secrets.toml`:\n\n"
            "```toml\n[anthropic]\napi_key = \"sk-ant-...\"\n```\n\n"
            "Get a key at [console.anthropic.com](https://console.anthropic.com)."
        )
    else:
        feedback_tab, chat_tab, plan_tab = st.tabs(
            ["📋 Post-Session Feedback", "💬 Chat", "🗓️ Training Plan"]
        )

        with feedback_tab:
            st.caption("Automatically generated right after each climb is logged.")
            feedback = st.session_state.get("last_coach_feedback")
            if feedback:
                st.markdown(feedback)
            else:
                st.info("Log a climb in the sidebar to get feedback here.")

        with chat_tab:
            st.caption(f"Grounded in {climber_name}'s logged climbs and personal bests.")

            if "coach_chat_history" not in st.session_state:
                st.session_state.coach_chat_history = []

            for msg in st.session_state.coach_chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if user_prompt := st.chat_input("Ask your coach anything..."):
                st.session_state.coach_chat_history.append({"role": "user", "content": user_prompt})
                with st.chat_message("user"):
                    st.markdown(user_prompt)
                with st.chat_message("assistant"):
                    chat_context = {
                        "climber_name": climber_name,
                        "climbing_history": load_all_records().get(climber_name, {}),
                    }
                    reply = st.write_stream(
                        ai_coach.stream_chat_reply(st.session_state.coach_chat_history, chat_context)
                    )
                st.session_state.coach_chat_history.append({"role": "assistant", "content": reply})

        with plan_tab:
            st.caption("Generates a structured multi-week plan from your personal records.")
            plan_weeks = st.slider("Plan length (weeks)", 2, 12, 4)
            plan_goal = st.text_input(
                "Primary goal", placeholder="e.g. send my first 5.12a, build finger strength"
            )
            if st.button("Generate Training Plan", use_container_width=True):
                with st.spinner("Building your plan..."):
                    try:
                        st.session_state.coach_training_plan = ai_coach.generate_training_plan(
                            climber_name,
                            load_all_records().get(climber_name, {}),
                            weeks=plan_weeks,
                            goal=plan_goal,
                        )
                    except Exception as exc:
                        st.error(f"Couldn't generate a plan: {exc}")

            plan = st.session_state.get("coach_training_plan")
            if plan:
                st.write(plan["summary"])
                for week in plan["weeks"]:
                    with st.expander(f"Week {week['week_number']}: {week['focus']}", expanded=False):
                        st.dataframe(
                            pd.DataFrame(week["sessions"]),
                            use_container_width=True,
                            hide_index=True,
                        )

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

with admin_tab:
    st.header("🔐 Admin")

    try:
        admin_secret = st.secrets.get("admin", {}).get("password")
    except Exception:
        admin_secret = None

    if not admin_secret:
        st.info(
            "Admin dashboard isn't configured. Add this to `.streamlit/secrets.toml` to enable it:\n\n"
            "```toml\n[admin]\npassword = \"choose-a-password\"\n```"
        )
    elif not st.session_state.get("admin_authed"):
        admin_pw = st.text_input("Password", type="password")
        if st.button("Unlock"):
            if admin_pw == admin_secret:
                st.session_state.admin_authed = True
                st.rerun()
            else:
                st.error("Wrong password.")
    else:
        all_feedback = load_feedback()
        all_sessions = get_sessions()

        st.write("### 💬 Feedback")
        if all_feedback:
            st.dataframe(pd.DataFrame(all_feedback), use_container_width=True, hide_index=True)
        else:
            st.info("No feedback submitted yet.")

        st.write("### ⏱️ Session Time")
        if all_sessions:
            sess_df = pd.DataFrame(all_sessions)
            s_col1, s_col2, s_col3 = st.columns(3)
            s_col1.metric("Total Sessions", len(sess_df))
            s_col2.metric("Total Time (hrs)", f"{sess_df['duration_min'].sum() / 60:.1f}")
            s_col3.metric("Avg Session (min)", f"{sess_df['duration_min'].mean():.0f}")
            st.dataframe(sess_df, use_container_width=True, hide_index=True)
        else:
            st.info("No sessions logged yet.")

        if all_feedback or all_sessions:
            if not ai_coach.is_configured():
                st.caption("Configure the AI Coach's Anthropic key to get an auto-generated summary here.")
            elif st.button("🤖 Summarize: where should this go next?"):
                with st.spinner("Thinking..."):
                    st.session_state.admin_summary = ai_coach.summarize_feedback(all_feedback, all_sessions)
            if st.session_state.get("admin_summary"):
                st.markdown(st.session_state.admin_summary)

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

    # ----------------- WORKSPACE SPLIT -----------------
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.write("### 📈 Climb History")

        if not climbs:
            st.info("No climbs logged yet. Use the sidebar to log your first one.")
        else:
            history_df = pd.DataFrame(climbs)[
                ["date", "discipline", "grade", "route_name", "status", "location"]
            ]
            history_df.columns = ["Date", "Discipline", "Grade", "Route/Problem", "Status", "Location"]
            st.dataframe(history_df, use_container_width=True, hide_index=True)

    with col_right:
        st.write("### 🧗 Grade Progression")

        if not climbs:
            st.info("Log a climb in the sidebar to see your progression here.")
        else:
            prog_df = pd.DataFrame(climbs)
            prog_df["Rank"] = prog_df.apply(lambda r: grade_rank(r["discipline"], r["grade"]), axis=1)
            prog_df = prog_df.sort_values("date")

            # Ordinal, not temporal: a bare "YYYY-MM-DD" string parsed as a
            # timestamp gets treated as UTC midnight, which the browser then
            # renders in local time - shifting the axis label onto the wrong
            # day/hour. Dates-as-categories sidesteps that; ISO strings still
            # sort correctly as text, so chronological order is unaffected.
            progression_chart = alt.Chart(prog_df).mark_line(point=True, interpolate="step-after").encode(
                x=alt.X("date:O", title="Date", sort=None),
                y=alt.Y("Rank:Q", title="Difficulty Rank"),
                color=alt.Color("discipline:N", title="Discipline", scale=alt.Scale(scheme="category10")),
                tooltip=["date", "discipline", "grade", "status", "route_name"],
            ).properties(height=360).interactive()

            st.altair_chart(progression_chart, use_container_width=True)
            st.caption("💡 Higher = harder within that discipline's own scale (V-scale or YDS).")