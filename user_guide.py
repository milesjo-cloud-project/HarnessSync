import streamlit as st

from grades import V_GRADES, YDS_GRADES, SEND_STATUSES


def render_hardware_manual_tab():
    """Renders the climb-logging walkthrough and grade-scale reference."""
    st.header("📖 Climb Log Guide")
    st.markdown("How to log a session and how the two grade scales work.")

    m_col1, m_col2, m_col3 = st.columns(3)

    with m_col1:
        st.markdown("### 📝 Step 1: Log a Climb")
        st.info(
            "In the sidebar, pick a discipline, grade, and send status, then hit "
            "**Log Climb**. Route/problem name and location are optional but make "
            "your history easier to skim later."
        )

    with m_col2:
        st.markdown("### 🧗 Step 2: Climb")
        st.warning(
            "Log as many climbs as you did that session - one entry per route or "
            "problem. There's no limit per day."
        )

    with m_col3:
        st.markdown("### 📊 Step 3: Review")
        st.success(
            "Check the Dashboard tab for your full history and grade progression, "
            "and the Leaderboard tab to see how you stack up against other climbers."
        )

    st.markdown("---")

    st.header("🪨 Bouldering: V-Scale")
    st.markdown(
        "Difficulty depends on the specific problem's structure, not just the "
        "number on the wall - pick whatever the gym or guidebook labeled it."
    )
    st.code(" · ".join(V_GRADES), language=None)

    st.markdown("---")

    st.header("🧗 Roped Climbing: Yosemite Decimal System (YDS)")
    st.markdown(
        "Used for top-rope and lead climbing. Grades from 5.10 up split into "
        "a/b/c/d sub-grades."
    )
    st.code(" · ".join(YDS_GRADES), language=None)

    st.markdown("---")

    st.header("🏁 Send Statuses")
    st.markdown(", ".join(f"**{s}**" for s in SEND_STATUSES))
    st.caption(
        "Flash = sent first try with no prior info. Redpoint = sent after "
        "previous attempts. Sent = completed, unspecified style. Fall = did not "
        "complete. Project = still working it."
    )

    st.markdown("---")
    st.caption("🔒 HarnessSync | Climb Log | Powered by Streamlit & the Claude API.")
