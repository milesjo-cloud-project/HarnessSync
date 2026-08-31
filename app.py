from datetime import date

import streamlit as st
import pandas as pd
import altair as alt

from grades import GRADES_BY_DISCIPLINE, SEND_STATUSES, grade_rank
from profile_manager import log_climb, get_climbs, load_all_records
from user_guide import render_hardware_manual_tab
from leaderboard_engine import compile_leaderboard
import ai_coach

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

# ----------------- MAIN PANEL HEADER -----------------
st.title("🧗 HarnessSync")
st.subheader("Climb Logging, Grade Progression & Leaderboards")

dashboard_tab, leaderboard_tab, coach_tab, guide_tab = st.tabs(
    ["📊 Dashboard", "🏆 Leaderboard", "🤖 AI Coach", "📖 Guide"]
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