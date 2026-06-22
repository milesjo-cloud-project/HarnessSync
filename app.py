import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
from datetime import datetime

# Path Configurations
PROFILES_DIR = "climber_profiles"
PR_FILE_PATH = os.path.join(PROFILES_DIR, "personal_records.json")

def setup_directories():
    if not os.path.exists(PROFILES_DIR):
        os.makedirs(PROFILES_DIR)
    if not os.path.exists(PR_FILE_PATH):
        with open(PR_FILE_PATH, 'w') as f:
            json.dump({}, f)

# Page Setup: Configure Dark Mode Aesthetic
st.set_page_config(page_title="HarnessSync | Climbing Analytics", layout="wide")
setup_directories()

# --- APPLICATION HEADER ---
st.title("🧗 HarnessSync Portal")
st.subheader("Transforming raw acceleration into climbing insights")
st.markdown("---")

# --- SIDEBAR: USER MANAGEMENT & DATA INPUT ---
st.sidebar.header("📥 Sync Station")
climber_name = st.sidebar.text_input("Climber Name:").strip().capitalize()
env_type = st.sidebar.radio("Select Environment:", ["Indoor", "Outdoor"])

uploaded_file = st.sidebar.file_saver = st.sidebar.file_uploader("Upload 'climb.csv'", type=["csv", "txt"])

# --- CORE PROCESSING PORTAL ---
if climber_name and uploaded_file:
    # 1. Read uploaded CSV data
    columns = ["Timestamp_ms", "X", "Y", "Z"]
    df = pd.read_csv(uploaded_file, names=columns)
    
    # Calculate physical data structures
    df['Elapsed_Time_Sec'] = (df['Timestamp_ms'] - df['Timestamp_ms'].iloc[0]) / 1000.0
    df['Total_G'] = (df['X']**2 + df['Y']**2 + df['Z']**2)**0.5

    total_duration = df['Elapsed_Time_Sec'].max()
    max_impact = df['Total_G'].max()
    average_strain = df['Total_G'].mean()

    # 2. Universal PR Ledger Management
    with open(PR_FILE_PATH, 'r') as f:
        all_records = json.load(f)
    if climber_name not in all_records:
        all_records[climber_name] = {
            "Indoor": {"longest_climb_sec": 0.0, "highest_impact_g": 0.0, "max_average_strain_g": 0.0},
            "Outdoor": {"longest_climb_sec": 0.0, "highest_impact_g": 0.0, "max_average_strain_g": 0.0}
        }
    
    user_prs = all_records[climber_name][env_type]
    pr_alerts = []

    # Record verification logic
    if total_duration > user_prs["longest_climb_sec"]:
        user_prs["longest_climb_sec"] = round(total_duration, 2)
        pr_alerts.append(f"⏱️ Longest {env_type} Endurance: {total_duration:.2f}s")
    if max_impact > user_prs["highest_impact_g"]:
        user_prs["highest_impact_g"] = round(max_impact, 2)
        pr_alerts.append(f"💥 Highest {env_type} Peak Force: {max_impact:.2f}g")
    if average_strain > user_prs["max_average_strain_g"]:
        user_prs["max_average_strain_g"] = round(average_strain, 2)
        pr_alerts.append(f"📈 Highest {env_type} Session Intensity: {average_strain:.2f}g")

    all_records[climber_name][env_type] = user_prs
    with open(PR_FILE_PATH, 'w') as f:
        json.dump(all_records, f, indent=4)

    # --- MAIN CONTENT DASHBOARD DISPLAY ---
    
    # Personal Record Celebrations
    if pr_alerts:
        for alert in pr_alerts:
            st.balloons()
            st.success(f"🏆 NEW PERSONAL RECORD DETECTED: {alert}")

    # Layout Row 1: Session Stat Cards
    st.header(f"📊 {climber_name}'s Session Analytics Summary ({env_type})")
    col1, col2, col3 = st.columns(3)
    col1.metric("Recorded Climbing Time", f"{total_duration:.2f} s")
    col2.metric("Average Route Strain", f"{average_strain:.2f} g")
    col3.metric("Maximum Peak Force", f"{max_impact:.2f} g")

    # Layout Row 2: Graph Display & New Climber Guide Side-By-Side
    st.markdown("---")
    graph_col, guide_col = st.columns([2, 1])

    with graph_col:
        st.subheader("📈 Movement Acceleration Vector Timeline")
        fig = px.line(
            df, 
            x='Elapsed_Time_Sec', 
            y=['X', 'Y', 'Z', 'Total_G'],
            labels={'Elapsed_Time_Sec': 'Time (Seconds)', 'value': 'Force (g)', 'variable': 'Axis'},
            title="Biomechanical Strain Profile"
        )
        fig.update_layout(template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    with guide_col:
        st.subheader("🎓 Beginner's Interpretation Guide")
        st.info(
            "📈 **Rhythmic Waves:** Consistent oscillations show smooth hip extensions "
            "and active vertical progression.\n\n"
            "🛑 **Flatlines (1.0g):** Horizontal sections show where you stopped moving "
            "to adjust your stance, chalk up, or rest your arms.\n\n"
            "💥 **Drop & Spike:** A sudden dip to 0g represents freefall, immediately followed "
            "by a steep peak when the catch occurs."
        )
        if env_type == "Outdoor":
            st.warning("🏔️ **Outdoor Notice:** Profiles usually present elongated resting cycles "
                       "and sharp acceleration shifts due to rock friction and multi-pitch durations.")
        else:
            st.success("🏠 **Indoor Notice:** Profiles showcase continuous, compact wave frequencies "
                       "reflecting uniform pacing on gym routes.")

else:
    # Onboarding instructions when app is blank
    st.info("👋 Welcome! To begin viewing analytics, enter a climber's name and drag-and-drop a data file in the sidebar menu.")