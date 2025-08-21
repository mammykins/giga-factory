# process_mining_analysis.py

import pandas as pd
import pm4py
from pm4py.algo.discovery.inductive import algorithm as inductive_miner
from pm4py.algo.conformance.alignments.petri_net import algorithm as alignments_module
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.visualization.petri_net import visualizer as pn_viz
from pm4py.statistics import start_activities
from pm4py.statistics import end_activities


# --- Load Event Log Data ---
try:
    event_log_df = pd.read_csv("battery_production_event_log.csv")
    print("\nLoaded event log from CSV.")
except FileNotFoundError:
    print("CSV not found, generating synthetic data again.")
    event_log_df = generate_battery_production_log(num_cases=1000)
    event_log_df.to_csv("battery_production_event_log.csv", index=False)

# Ensure timestamp column is datetime
event_log_df["timestamp"] = pd.to_datetime(event_log_df["timestamp"])


# --- Convert DataFrame → EventLog ---
# IMPORTANT: PM4Py expects *canonical column names*:
#   - case:concept:name  -> case identifier
#   - concept:name       -> activity name
#   - time:timestamp     -> timestamp
# If you rename your DataFrame this way, you don't need to pass any mapping constants.
event_log_df = event_log_df.rename(columns={
    "case_id": "case:concept:name",
    "activity": "concept:name",
    "timestamp": "time:timestamp"
})

# Convert to EventLog object
event_log = log_converter.apply(event_log_df, variant=log_converter.Variants.TO_EVENT_LOG)

print("\nPM4Py EventLog Created:")
print(event_log)

# --- Process Discovery ---
print("\nDiscovering Process Model (Inductive Miner)...")

# Step 1: discover process tree
process_tree = inductive_miner.apply(event_log, variant=inductive_miner.Variants.IMf)

# Step 2: convert process tree into Petri net + initial/final marking
from pm4py.objects.conversion.process_tree import converter as pt_converter
petri_net, initial_marking, final_marking = pt_converter.apply(process_tree)

print("Process model discovered and converted to Petri Net.")

# --- Process Insights ---
print("\n--- Key Process Insights ---")

# 1. Most Frequent Activities
print("\n1. Most Frequent Activities:")
print(event_log_df["concept:name"].value_counts().head(10))

# 2. Start and End Activities
print("\n2. Start and End Activities:")
start_activities = start_activities.get_start_activities(event_log)
end_activities = end_activities.get_end_activities(event_log)
print(f"  Start Activities: {start_activities}")
print(f"  End Activities: {end_activities}")

# 3. Average Duration per Activity
print("\n3. Average Duration per Activity:")
event_log_df["duration_seconds"] = (
    event_log_df.groupby("case:concept:name")["time:timestamp"]
    .diff()
    .dt.total_seconds()
    .fillna(0)
).abs()

activity_durations = (
    event_log_df[event_log_df["concept:name"].str.startswith("REWORK_") == False]
    .groupby("concept:name")["duration_seconds"]
    .agg(["mean", "median", "std", "count"])
)
activity_durations["mean_minutes"] = activity_durations["mean"] / 60
activity_durations["median_minutes"] = activity_durations["median"] / 60
print(activity_durations.sort_values(by="mean_minutes", ascending=False).head(10))

# 4. Rework Analysis
print("\n4. Rework Analysis:")
rework_events = event_log_df[event_log_df["concept:name"].str.startswith("REWORK_")]
if not rework_events.empty:
    print(rework_events["concept:name"].value_counts())
else:
    print("No rework events found in the synthetic data.")


# --- Conformance Checking ---
print("\n5. Conformance Checking:")

alignments = alignments_module.apply(event_log, petri_net, initial_marking, final_marking)

print("  Calculating Replay Fitness...")
fitness_results = pm4py.algo.evaluation.replay_fitness.algorithm.apply(
    event_log, petri_net, initial_marking, final_marking
)
print(f"    Log Fitness: {fitness_results['averageFitness']:.4f}")

print("  Calculating Precision...")
precision_results = pm4py.algo.evaluation.precision.algorithm.apply(
    event_log, petri_net, initial_marking, final_marking
)
print(f"    Precision: {precision_results:.4f}")

print("  Calculating Generalization...")
generalization_results = pm4py.algo.evaluation.generalization.algorithm.apply(
    event_log, petri_net, initial_marking, final_marking
)
print(f"    Generalization: {generalization_results:.4f}")

print("  Calculating Robustness...")
robustness_results = pm4py.algo.evaluation.robustness.algorithm.apply(
    event_log, petri_net, initial_marking, final_marking
)
print(f"    Robustness: {robustness_results:.4f}")


# --- Batch Size Analysis ---
print("\n6. Analysis of Batch Size and Process Duration:")

trace_durations_df = event_log_df.groupby("case:concept:name").agg(
    first_timestamp=("time:timestamp", "min"),
    last_timestamp=("time:timestamp", "max"),
    batch_size=("batch_size", lambda x: x.iloc[0]),
)
trace_durations_df["total_duration_seconds"] = (
    trace_durations_df["last_timestamp"] - trace_durations_df["first_timestamp"]
).dt.total_seconds()
trace_durations_df["total_duration_minutes"] = (
    trace_durations_df["total_duration_seconds"] / 60
)

print("  Overall batch processing time vs. batch size:")
print(trace_durations_df[["batch_size", "total_duration_minutes"]].corr())

event_log_df_with_batch = event_log_df.merge(
    trace_durations_df[["batch_size"]],
    left_on="case:concept:name",
    right_index=True,
    how="left",
)

# Assembly/Packaging duration vs batch size
assembly_df = event_log_df_with_batch[
    event_log_df_with_batch["concept:name"] == "Assembly/Packaging"
]
if not assembly_df.empty:
    assembly_df["batch_size_group"] = pd.cut(
        assembly_df["batch_size"], bins=5, labels=False, include_lowest=True
    )
    avg_assembly_duration_by_group = (
        assembly_df.groupby("batch_size_group")["duration_seconds"].mean() / 60
    )
    print("\n  Average Assembly/Packaging duration (minutes) by batch size group:")
    print(avg_assembly_duration_by_group)

# Rework rate vs batch size
rework_events_with_batch = event_log_df_with_batch[
    event_log_df_with_batch["concept:name"].str.startswith("REWORK_")
]
if not rework_events_with_batch.empty:
    rework_events_with_batch["batch_size_group"] = pd.cut(
        rework_events_with_batch["batch_size"], bins=5, labels=False, include_lowest=True
    )
    rework_rate_by_batch_group = (
        rework_events_with_batch.groupby("batch_size_group")["case:concept:name"].count()
    )
    total_batches_in_group = (
        event_log_df_with_batch.groupby("batch_size_group")["case:concept:name"].nunique()
    )
    rework_occurrence_rate = (
        (rework_rate_by_batch_group / total_batches_in_group).fillna(0) * 100
    )
    print("\n  Rework occurrence rate (%) by batch size group:")
    print(rework_occurrence_rate)
