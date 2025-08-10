import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_battery_production_log(num_cases=500):
    """
    Generates a synthetic event log for battery production.
    """
    data = []
    start_date = datetime(2023, 10, 1, 0, 0, 0) # Start date for the log

    activities = {
        "Raw Material Arrival": {"duration": (5, 30), "chance": 1.0, "rework_to": None},
        "Quality Check (Raw Material)": {"duration": (15, 60), "chance": 1.0, "rework_to": "Raw Material Arrival"},
        "Storage (Raw Material)": {"duration": (30, 120), "chance": 0.95, "rework_to": None}, # 5% might go directly
        "Material Allocation": {"duration": (10, 45), "chance": 1.0, "rework_to": "Quality Check (Raw Material)"}, # Rework if QC failed
        "Production Batch Start": {"duration": (0, 0), "chance": 1.0, "rework_to": None}, # Placeholder for start
        "In-Process Quality Check": {"duration": (20, 90), "chance": 1.0, "rework_to": "Production Batch Start"},
        "Assembly/Packaging": {"duration": (60, 300), "chance": 1.0, "rework_to": "In-Process Quality Check"},
        "Final Quality Check": {"duration": (15, 75), "chance": 1.0, "rework_to": "Assembly/Packaging"},
        "Storage (Finished Goods)": {"duration": (45, 180), "chance": 0.98, "rework_to": None}, # 2% might go directly to fulfillment
        "Order Fulfillment": {"duration": (20, 150), "chance": 1.0, "rework_to": "Storage (Finished Goods)"},
        "Shipment": {"duration": (5, 60), "chance": 1.0, "rework_to": None}
    }

    resources = ["Worker A", "Worker B", "Machine X", "Machine Y", "Warehouse Staff 1"]
    rework_prob = 0.15 # Probability of rework at a specific step if rework_to is defined

    for i in range(num_cases):
        case_id = f"BATCH_{i+1:05d}"
        current_time = start_date
        batch_size = random.randint(500, 5000) # Batteries per batch

        # Simulate Production Batch Start
        start_activity = "Production Batch Start"
        data.append({
            "case_id": case_id,
            "activity": start_activity,
            "timestamp": current_time,
            "resource": random.choice(resources),
            "batch_size": batch_size
        })

        # Simulate Raw Material Arrival as a prerequisite
        material_arrival_time = current_time - timedelta(days=random.uniform(0.1, 0.5))
        data.append({
            "case_id": case_id,
            "activity": "Raw Material Arrival",
            "timestamp": material_arrival_time,
            "resource": random.choice(resources),
            "batch_size": batch_size
        })
        current_time = material_arrival_time # Ensure production starts after material arrival

        # Pathfinding through the process
        process_path = list(activities.keys())
        # Reorder for logical flow, and ensure dependencies are met if simulating rework
        # This is a simplified flow. Real process mining tools infer the flow.
        # For synthetic data, we define a plausible flow.
        logical_flow = [
            "Raw Material Arrival", "Quality Check (Raw Material)",
            "Storage (Raw Material)", "Material Allocation",
            "Production Batch Start", "In-Process Quality Check",
            "Assembly/Packaging", "Final Quality Check",
            "Storage (Finished Goods)", "Order Fulfillment", "Shipment"
        ]

        # Let's adjust the logical flow a bit for better simulation
        # Some steps are always followed, some have chances or rework loops

        # First, Raw Materials path
        current_activity_idx = logical_flow.index("Raw Material Arrival")
        prev_timestamp = current_time # time of Raw Material Arrival

        while logical_flow[current_activity_idx] not in ["Production Batch Start", "Shipment"]:
            current_activity = logical_flow[current_activity_idx]
            activity_config = activities[current_activity]

            # Decide if the activity happens (chance > 0.0)
            if random.random() < activity_config["chance"]:
                # Simulate duration and potential delays
                duration_minutes = random.uniform(*activity_config["duration"])
                time_delta = timedelta(minutes=duration_minutes)
                event_timestamp = prev_timestamp + time_delta

                # Add rework loop if applicable and rework happens
                if activity_config["rework_to"] and random.random() < rework_prob:
                    print(f"Rework for {case_id} at {current_activity}!")
                    # Simulate rework by sending it back to a previous step
                    # Find the index of the rework_to activity
                    rework_idx = logical_flow.index(activity_config["rework_to"])
                    # Add rework event
                    data.append({
                        "case_id": case_id,
                        "activity": f"REWORK_{current_activity}", # Mark as rework event
                        "timestamp": event_timestamp,
                        "resource": random.choice(resources),
                        "batch_size": batch_size
                    })
                    current_activity_idx = rework_idx # Go back in the flow
                    prev_timestamp = event_timestamp # Rework starts from here
                    continue # Skip to next iteration with new current_activity_idx

                # Normal activity processing
                data.append({
                    "case_id": case_id,
                    "activity": current_activity,
                    "timestamp": event_timestamp,
                    "resource": random.choice(resources),
                    "batch_size": batch_size
                })
                prev_timestamp = event_timestamp
                current_activity_idx += 1 # Move to the next step in the logical flow
            else:
                # Activity skipped (due to chance), move to next logical step
                current_activity_idx += 1

            # Ensure we don't go out of bounds
            if current_activity_idx >= len(logical_flow):
                break

        # Now simulate the core production path from Production Batch Start to Shipment
        # We'll ensure the 'Production Batch Start' is correctly placed if we jumped back for rework

        # Find the actual start time for the core production process
        core_production_start_time = None
        for event in reversed(data):
            if event["case_id"] == case_id and event["activity"] == "Production Batch Start":
                core_production_start_time = event["timestamp"]
                prev_timestamp = event["timestamp"] # Ensure correct start for the next phase
                break

        if core_production_start_time is None: # Should not happen if initial start was added
            continue

        # Resume from after "Production Batch Start"
        current_activity_idx = logical_flow.index("Production Batch Start") + 1

        while current_activity_idx < len(logical_flow):
            current_activity = logical_flow[current_activity_idx]
            activity_config = activities[current_activity]

            # Skip activities that are before the actual start of production in this iteration
            if current_activity == "Production Batch Start":
                current_activity_idx += 1
                continue

            # Decide if the activity happens (chance > 0.0)
            if random.random() < activity_config["chance"]:
                duration_minutes = random.uniform(*activity_config["duration"])
                time_delta = timedelta(minutes=duration_minutes)
                event_timestamp = prev_timestamp + time_delta

                # Handle rework for production steps
                if activity_config["rework_to"] and random.random() < rework_prob:
                    print(f"Rework for {case_id} at {current_activity}!")
                    data.append({
                        "case_id": case_id,
                        "activity": f"REWORK_{current_activity}",
                        "timestamp": event_timestamp,
                        "resource": random.choice(resources),
                        "batch_size": batch_size
                    })

                    # Find the index of the rework_to activity in the logical flow
                    # We need to find the activity that logically precedes the current one
                    # This is tricky with rework. Let's assume rework goes back to the immediately preceding step's prerequisite.
                    if current_activity == "In-Process Quality Check": rework_target_activity = "Production Batch Start"
                    elif current_activity == "Assembly/Packaging": rework_target_activity = "In-Process Quality Check"
                    elif current_activity == "Final Quality Check": rework_target_activity = "Assembly/Packaging"
                    elif current_activity == "Order Fulfillment": rework_target_activity = "Storage (Finished Goods)"
                    else: rework_target_activity = current_activity # Fallback

                    try:
                        rework_idx = logical_flow.index(rework_target_activity)
                        current_activity_idx = rework_idx + 1 # Next step after rework target
                        prev_timestamp = event_timestamp # Rework starts from here
                    except ValueError: # If rework_target_activity not found, just continue after current
                        current_activity_idx += 1
                        prev_timestamp = event_timestamp

                    continue # Restart the loop for the new current_activity_idx

                # Normal activity processing
                data.append({
                    "case_id": case_id,
                    "activity": current_activity,
                    "timestamp": event_timestamp,
                    "resource": random.choice(resources),
                    "batch_size": batch_size
                })
                prev_timestamp = event_timestamp
                current_activity_idx += 1
            else:
                # Activity skipped, move to next logical step
                current_activity_idx += 1

        # Ensure there's at least one path from start to finish.
        # The logic above tries to connect them, but edge cases exist.
        # For simplicity here, we assume the logical_flow defines the path and rework loops.

    df = pd.DataFrame(data)
    df = df.sort_values(by=['case_id', 'timestamp'])
    return df

# Generate the data
synthetic_log_df = generate_battery_production_log(num_cases=1000)
print("Synthetic Event Log Created:")
print(synthetic_log_df.head())
print(f"\nTotal events: {len(synthetic_log_df)}")
print(f"Unique cases (batches): {synthetic_log_df['case_id'].nunique()}")

# Save to CSV for potential future use or sharing
synthetic_log_df.to_csv("battery_production_event_log.csv", index=False)
