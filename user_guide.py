import streamlit as st
import pandas as pd

from grades import V_GRADES, YDS_GRADES, SEND_STATUSES, BOULDER_CONVERSION, ROPE_CONVERSION


def render_hardware_manual_tab():
    """Renders the climb-logging walkthrough, grade conversion tables, and send status definitions."""
    st.header("📖 Climbing Reference & Conversion Matrix")
    st.caption("International grade scale equivalencies, send definitions, and app guide.")

    tab1, tab2, tab3 = st.tabs(["🔀 Grade Conversion Matrix", "🏁 Send Terminology", "📝 How to Log"])

    with tab1:
        st.subheader("Bouldering Grade Equivalencies (V-Scale ↔ Font)")
        st.caption("V-Scale is standard in the Americas & Australia; Font (Fontainebleau) is standard in Europe.")
        boulder_df = pd.DataFrame(BOULDER_CONVERSION)
        boulder_df.columns = ["V-Scale (USA)", "Font Scale (EUR)", "Experience Level"]
        st.dataframe(boulder_df, use_container_width=True, hide_index=True)

        st.markdown("---")

        st.subheader("Roped Grade Equivalencies (YDS ↔ French)")
        st.caption("Yosemite Decimal System (YDS) is standard in North America; French scale is international.")
        rope_df = pd.DataFrame(ROPE_CONVERSION)
        rope_df.columns = ["YDS (North America)", "French Scale (International)", "Difficulty Tier"]
        st.dataframe(rope_df, use_container_width=True, hide_index=True)

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

    st.markdown("---")
    st.caption("🔒 HarnessSync | Intelligent Climbing Log")

