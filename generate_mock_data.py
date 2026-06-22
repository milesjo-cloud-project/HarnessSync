import numpy as np
import pandas as pd

def generate_mock_climb_data(filename="climb.csv"):
    print("Generating synthetic climbing session data...")
    
    # 20 Hz sampling rate means a reading every 50ms (0.05 seconds)
    time_step = 50  # milliseconds
    total_duration_sec = 60  # 1 minute total simulation
    total_readings = int((total_duration_sec * 1000) / time_step)
    
    timestamps = []
    x_axis = []
    y_axis = []
    z_axis = []
    
    # Base timestamp starting in 2026
    start_ms = 1773993600000 
    
    for i in range(total_readings):
        current_time = start_ms + (i * time_step)
        elapsed_sec = (i * time_step) / 1000.0
        timestamps.append(current_time)
        
        # --- SIMULATING THE CLIMBING STAGES ---
        
        # Phase 1: Steady, rhythmic climbing (0 to 25 seconds)
        if 0 <= elapsed_sec < 25:
            # Gravity splits across axes; Z is mostly upright (1.0g baseline)
            # Rhythmic waves simulate shifting hips and moving upward
            x = 0.0 + np.sin(elapsed_sec * 2) * 0.15 + np.random.normal(0, 0.05)
            y = 0.0 + np.sin(elapsed_sec * 1.5) * 0.25 + np.random.normal(0, 0.05)
            z = 1.0 + np.sin(elapsed_sec * 2) * 0.3 + np.random.normal(0, 0.05)
            
        # Phase 2: The Standstill Rest (25 to 40 seconds)
        elif 25 <= elapsed_sec < 40:
            # Climber stops to look for holds or shake out arms
            # Near-zero variance, resting close to standard 1.0g gravity baseline
            x = 0.0 + np.random.normal(0, 0.01)
            y = 0.0 + np.random.normal(0, 0.01)
            z = 1.0 + np.random.normal(0, 0.01)
            
        # Phase 3: The Lead Fall Event (40 to 43 seconds)
        elif 40 <= elapsed_sec < 43:
            # Split-second breakdown of a fall sequence:
            if 40.0 <= elapsed_sec < 40.5:
                # 1. Normal climbing tension just before slipping
                x, y, z = 0.1, -0.1, 1.1
            elif 40.5 <= elapsed_sec < 41.2:
                # 2. Weightlessness (Freefall) -> Accelerometer drops close to 0g
                x = 0.0 + np.random.normal(0, 0.02)
                y = 0.0 + np.random.normal(0, 0.02)
                z = 0.1 + np.random.normal(0, 0.02)
            elif 41.2 <= elapsed_sec < 41.5:
                # 3. Dynamic impact! The rope catches -> massive deceleration spike
                x = 1.2 + np.random.normal(0, 0.1)
                y = -1.5 + np.random.normal(0, 0.1)
                z = 4.2 + np.random.normal(0, 0.1)  # 4.2g spike on vertical axis
            else:
                # 4. Post-fall swinging/bouncing hanging on the rope
                decay = np.exp(-(elapsed_sec - 41.5) * 2)
                x = 0.0 + np.sin(elapsed_sec * 8) * 0.4 * decay
                y = 0.0 + np.cos(elapsed_sec * 8) * 0.5 * decay
                z = 1.0 + np.sin(elapsed_sec * 5) * 0.6 * decay
                
        # Phase 4: Controlled lowering/hanging static (43 to 60 seconds)
        else:
            x = 0.0 + np.random.normal(0, 0.02)
            y = 0.0 + np.random.normal(0, 0.02)
            z = 1.0 + np.random.normal(0, 0.02)
            
        x_axis.append(round(x, 4))
        y_axis.append(round(y, 4))
        z_axis.append(round(z, 4))

    # Construct the data frame matching our Arduino text layout
    df = pd.DataFrame({
        "Timestamp": timestamps,
        "X": x_axis,
        "Y": y_axis,
        "Z": z_axis
    })
    
    # Save as headerless CSV to mimic raw data dumps
    df.to_csv(filename, header=False, index=False)
    print(f"Success! Mock data saved to '{filename}'.")

if __name__ == "__main__":
    generate_mock_climb_data()