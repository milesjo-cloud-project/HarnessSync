import pandas as pd
import plotly.express as px
import os
import json
from datetime import datetime

PROFILES_DIR = "climber_profiles"
PR_FILE_PATH = os.path.join(PROFILES_DIR, "personal_records.json")

def setup_directories():
    if not os.path.exists(PROFILES_DIR):
        os.makedirs(PROFILES_DIR)
    if not os.path.exists(PR_FILE_PATH):
        with open(PR_FILE_PATH, 'w') as f:
            json.dump({}, f)

def check_and_update_environment_prs(climber_name, env_type, current_duration, current_max_g, current_avg_g):
    """Tracks separate personal records for Indoor and Outdoor sessions."""
    setup_directories()
    name_key = climber_name.strip().capitalize()
    
    with open(PR_FILE_PATH, 'r') as f:
        all_records = json.load(f)
        
    # Initialize profile structure if new
    if name_key not in all_records:
        all_records[name_key] = {
            "Indoor": {"longest_climb_sec": 0.0, "highest_impact_g": 0.0, "max_average_strain_g": 0.0},
            "Outdoor": {"longest_climb_sec": 0.0, "highest_impact_g": 0.0, "max_average_strain_g": 0.0}
        }
    
    # Catch older profiles that might not have separate Indoor/Outdoor keys yet
    if env_type not in all_records[name_key]:
        all_records[name_key][env_type] = {"longest_climb_sec": 0.0, "highest_impact_g": 0.0, "max_average_strain_g": 0.0}
        
    user_env_prs = all_records[name_key][env_type]
    new_records_broken = []
    
    if current_duration > user_env_prs["longest_climb_sec"]:
        user_env_prs["longest_climb_sec"] = round(current_duration, 2)
        new_records_broken.append(f"⏱️ Longest {env_type} Endurance: {current_duration:.2f}s")
        
    if current_max_g > user_env_prs["highest_impact_g"]:
        user_env_prs["highest_impact_g"] = round(current_max_g, 2)
        new_records_broken.append(f"💥 Highest {env_type} Peak Force: {current_max_g:.2f}g")
        
    if current_avg_g > user_env_prs["max_average_strain_g"]:
        user_env_prs["max_average_strain_g"] = round(current_avg_g, 2)
        new_records_broken.append(f"📈 Highest {env_type} Dynamic Intensity: {current_avg_g:.2f}g")
        
    all_records[name_key][env_type] = user_env_prs
    with open(PR_FILE_PATH, 'w') as f:
        json.dump(all_records, f, indent=4)
        
    return new_records_broken

def archive_session_to_profile(raw_file_path, climber_name, env_type):
    setup_directories()
    climber_folder = os.path.join(PROFILES_DIR, climber_name.strip().capitalize())
    if not os.path.exists(climber_folder):
        os.makedirs(climber_folder)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # File name explicitly logs whether it was an indoor or outdoor pitch
    archived_filename = f"climb_{env_type}_{timestamp}.csv"
    destination_path = os.path.join(climber_folder, archived_filename)
    
    try:
        columns = ["Timestamp_ms", "X", "Y", "Z"]
        df = pd.read_csv(raw_file_path, names=columns)
        df.to_csv(destination_path, index=False, header=False)
        print(f"💾 Session safely saved under {climber_name.capitalize()}'s {env_type} history!")
        return destination_path
    except Exception as e:
        print(f"❌ Error archiving data: {e}")
        return None

def analyze_climbing_session(file_path, climber_name, env_type):
    columns = ["Timestamp_ms", "X", "Y", "Z"]
    df = pd.read_csv(file_path, names=columns)
    
    df['Elapsed_Time_Sec'] = (df['Timestamp_ms'] - df['Timestamp_ms'].iloc[0]) / 1000.0
    df['Total_G'] = (df['X']**2 + df['Y']**2 + df['Z']**2)**0.5

    total_duration = df['Elapsed_Time_Sec'].max()
    max_impact = df['Total_G'].max()
    average_strain = df['Total_G'].mean()

    # Contextual tips based on environment
    print("\n" + "="*65)
    print(f"🧗 PROFILE ANALYTICS: {climber_name.upper()} | ENVIRONMENT: {env_type.upper()}")
    print("="*65)
    if env_type == "Outdoor":
        print("💡 CRAG INTERPRETATION TIP:")
        print("   Outdoor rock profiles show highly prolonged resting flatlines.")
        print("   Look closely for massive, sharp spikes—these indicate real lead falls")
        print("   or rock clipping deceleration forces.")
    else:
        print("💡 GYM INTERPRETATION TIP:")
        print("   Gym profiles emphasize rapid, continuous move cycles.")
        print("   Look for highly uniform, cyclic wave oscillations showing")
        print("   how efficiently you moved up the preset plastic holds.")
    print("="*65)

    print(f"\n⏱️ Recorded Time: {total_duration:.2f} seconds")
    print(f"📈 Average Structural Intensity: {average_strain:.2f} g")
    print(f"💥 Maximum Peak Impact: {max_impact:.2f} g")

    # Environment PR check
    records_broken = check_and_update_environment_prs(climber_name, env_type, total_duration, max_impact, average_strain)
    if records_broken:
        print("\n🏆🎉 OUTSTANDING! NEW ENVIRONMENT RECORD DETECTED! 🎉🏆")
        for record in records_broken:
            print(f"   🔥 {record}")
    else:
        print(f"\n⚡ Session parsed! Your {env_type} all-time records remain unbeaten.")

    # Render localized graph window
    fig = px.line(
        df, 
        x='Elapsed_Time_Sec', 
        y=['X', 'Y', 'Z', 'Total_G'],
        title=f"Movement Analysis ({env_type}) — Climber: {climber_name.capitalize()}"
    )
    fig.update_layout(template="plotly_dark", hovermode="x unified")
    fig.show()

if __name__ == "__main__":
    raw_hardware_file = "climb.csv"
    
    if not os.path.exists(raw_hardware_file):
        print(f"🔴 Run your generator or paste '{raw_hardware_file}' here to sync.")
    else:
        print("📥 --- ADVANCED CLIMBER PROFILE PORTAL ---")
        name_input = input("Enter the name of the climber: ")
        
        if name_input.strip() != "":
            print("\nSelect Environment:")
            print("1. Indoor Gym")
            print("2. Outdoor Crag/Rock")
            choice = input("Enter choice (1 or 2): ")
            
            env_type = "Indoor" if choice.strip() == "1" else "Outdoor"
            
            saved_profile_file = archive_session_to_profile(raw_hardware_file, name_input, env_type)
            if saved_profile_file:
                analyze_climbing_session(saved_profile_file, name_input, env_type)

def print_profile_dashboard_hub(climber_name):
    """Prints a structured multi-environment dashboard summary for the climber."""
    setup_directories()
    name_key = climber_name.strip().capitalize()
    
    if not os.path.exists(PR_FILE_PATH):
        return

    with open(PR_FILE_PATH, 'r') as f:
        all_records = json.load(f)
        
    if name_key not in all_records:
        print(f"\nℹ️ No historical profile data found yet for {name_key}.")
        return

    profile = all_records[name_key]
    
    # Extract split-environment records safely
    indoor = profile.get("Indoor", {"longest_climb_sec": 0.0, "highest_impact_g": 0.0, "max_average_strain_g": 0.0})
    outdoor = profile.get("Outdoor", {"longest_climb_sec": 0.0, "highest_impact_g": 0.0, "max_average_strain_g": 0.0})

    print("\n" + "═"*65)
    print(f"📊   {name_key.upper()}'S ALL-TIME CLIMBING PROFILE LEADERBOARD   📊")
    print("═"*65)
    
    # Structured Layout Grid for Easy Scanning
    print(f"{'METRIC TYPE':<30} | {'🏠 INDOOR GYM':<15} | {'🏔️ OUTDOOR CRAG':<15}")
    print("─"*65)
    print(f"{'Longest Endurance Duration':<30} | {str(indoor['longest_climb_sec'])+'s':<15} | {str(outdoor['longest_climb_sec'])+'s':<15}")
    print(f"{'Highest Peak Impact (Fall Catch)':<30} | {str(indoor['highest_impact_g'])+'g':<15} | {str(outdoor['highest_impact_g'])+'g':<15}")
    print(f"{'Max Session Intensity Strain':<30} | {str(indoor['max_average_strain_g'])+'g':<15} | {str(outdoor['max_average_strain_g'])+'g':<15}")
    print("═"*65)