import streamlit as st
import pandas as pd

from grades import BOULDER_CONVERSION, ROPE_CONVERSION


def render_hardware_manual_tab():
    """Renders the climb-logging walkthrough, grade conversion tables, and send status definitions."""
    st.header("📖 Climbing Reference & Conversion Matrix")
    st.caption("International grade scale equivalencies, send definitions, and app guide.")

    tab1, tab2, tab3, tab4 = st.tabs(["🔀 Grade Conversion Matrix", "🏁 Send Terminology", "📝 How to Log", "🔒 Privacy"])

    with tab1:
        st.subheader("Bouldering Grade Equivalencies (V-Scale ↔ Font)")
        st.caption("V-Scale is standard in the Americas & Australia; Font (Fontainebleau) is standard in Europe.")
        boulder_df = pd.DataFrame(BOULDER_CONVERSION)
        boulder_df.columns = ["V-Scale (USA)", "Font Scale (EUR)", "Experience Level"]
        st.dataframe(boulder_df, width="stretch", hide_index=True)

        st.markdown("---")

        st.subheader("Roped Grade Equivalencies (YDS ↔ French)")
        st.caption("Yosemite Decimal System (YDS) is standard in North America; French scale is international.")
        rope_df = pd.DataFrame(ROPE_CONVERSION)
        rope_df.columns = ["YDS (North America)", "French Scale (International)", "Difficulty Tier"]
        st.dataframe(rope_df, width="stretch", hide_index=True)

    with tab2:
        st.subheader("🏁 Send Status Definitions")
        st.markdown("""
        - **Onsight**: Sending a route cleanly on your **very first attempt**, with **zero prior knowledge**, beta, or watching anyone else climb it.
        - **Flash**: Sending a route cleanly on your **first attempt**, but having seen beta, watched a video, or received tips.
        - **Redpoint**: Cleanly sending a route (lead or top-rope) from bottom to top without falling or resting on gear, after previous failed attempts.
        - **Sent**: Completed the climb cleanly without taking rests, regardless of attempt style.
        - **Project**: Working a route across multiple tries or sessions without a clean send yet.
        - **Attempt**: Logging an individual practice run on a route.
        """)

    with tab3:
        st.subheader("📝 Step-by-Step Logging Guide")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("### 1️⃣ Log a Climb / Session")
            st.info("Use the sidebar form to log individual sends or projects. Record the grade, environment (Gym vs Outdoor), wall angle, and hold types.")
        with col2:
            st.markdown("### 2️⃣ Track Projects")
            st.warning("Use the **🎯 Projects** tab to track ongoing projects, increment attempt counts, and log beta notes until you send it.")
        with col3:
            st.markdown("### 3️⃣ Analyze Pyramid & Progress")
            st.success("Check the **📊 Dashboard** for your Send Volume Pyramid chart to ensure you are building a strong pyramid base before pushing higher grades.")

    with tab4:
        st.subheader("🔒 Your Data")
        st.markdown("""
        - **What's stored:** your sign-in email, the display name you choose, and the climbs, projects,
          sessions and feedback you log.
        - **Who can see it:** your climb log, projects and sessions are visible only to you. If you opt in,
          your **display name, best grade and send count** appear on the public leaderboard - never your email.
        - **Feedback** you send is emailed to the developer along with your email address, so they can reply.
        - **Your control:** hide yourself from the leaderboard, download your climbs as CSV, or permanently
          delete your account and all its data from the 👤 menu in the sidebar.
        """)

    st.markdown("---")
    st.caption("🔒 HarnessSync | Intelligent Climbing Log")

