# process_mining_analysis.py
# ----------------------------------------------------------
# Battery manufacturing process mining analysis
#
# This script does three things:
# 1) Converts a tabular event log (CSV) into a PM4Py EventLog
# 2) Discovers and visualizes the process model (Inductive Miner -> Petri Net)
# 3) Runs diagnostics (frequent activities, start/end acts, durations, rework)
# 4) Analyzes how batch size correlates with performance (stakeholder value!)
#
# Comments are written with the "why" in mind, not just the "what".
# ----------------------------------------------------------

import pandas as pd
import pm4py

# Process discovery
from pm4py.algo.discovery.inductive import algorithm as inductive_miner
from pm4py.objects.conversion.process_tree import converter as pt_converter

# Log conversion (DataFrame -> EventLog)
from pm4py.objects.conversion.log import converter as log_converter

# Conformance checking
from pm4py.algo.conformance.alignments.petri_net import algorithm as alignments_module
from pm4py.algo.evaluation import algorithm as eval_algorithm

# Visualization
from pm4py.visualization.petri_net import visualizer as pn_viz

# Start / End activities
from pm4py.statistics.start_activities.log import get as start_acts_get
from pm4py.statistics.end_activities.log import get as end_acts_get


# ---------------------------
# 1) Load the event log
# ---------------------------
try:
    event_log_df = pd.read_csv("battery_production_event_log.csv")
    print("\nLoaded event log from CSV.")
except FileNotFoundError:
    raise FileNotFoundError(
        "CSV not found. Please provide 'battery_production_event_log.csv' "
        "before running this script."
    )

# Ensure timestamps are proper datetime
event_log_df["timestamp"] = pd.to_datetime(event_log_df["timestamp"])

# ----------------------------------------------------------
# 2) Convert DataFrame -> EventLog using canonical XES names
# WHY: PM4Py works best when columns match XES semantics.
# - case_id -> case:concept:name
# - activity -> concept:name
# - timestamp -> time:timestamp
# ----------------------------------------------------------
df = event_log_df.rename(
    columns={
        "case_id": "case:concept:name",
        "activity": "concept:name",
        "timestamp": "time:timestamp",
    }
)

# Convert into PM4Py EventLog (object-based, not just tabular)
event_log = log_converter.apply(df, variant=log_converter.Variants.TO_EVENT_LOG)
print("Converted DataFrame into PM4Py EventLog.")

# ------------------------------------------------------------
# 3) Process discovery (Inductive Miner -> Process Tree -> Petri Net)
# WHY: The Petri net is a formal model we can check for conformance.
# ------------------------------------------------------------
print("\nDiscovering Process Model (Inductive Miner)...")
process_tree = inductive_miner.apply(event_log, variant=inductive_miner.Variants.IMf)
petri_net, initial_marking, final_marking = pt_converter.apply(process_tree)
print("Process model discovered and converted to Petri Net.")

# ---------------------------------------------
# 4) Visualize Petri Net
# WHY: Stakeholders like pictures. This shows the "happy path".
# ---------------------------------------------
try:
    gviz = pn_viz.apply(petri_net, initial_marking, final_marking)
    pn_viz.save(gviz, "discovered_process_model.png")
    print("Petri net visualization saved to 'discovered_process_model.png'.")
except Exception as e:
    print(f"Petri net visualization skipped: {e}")

# --------------------------------
# 5) Exploratory diagnostics
# --------------------------------
print("\n--- Key Process Insights ---")

# 5.1 Most frequent activities
print("\n1. Most Frequent Activities:")
print(df["concept:name"].value_counts().head(10))

# 5.2 Start/End activities
print("\n2. Start and End Activities:")
print("  Start Activities:", start_acts_get.get_start_activities(event_log))
print("  End Activities:  ", end_acts_get.get_end_activities(event_log))

# 5.3 Average duration per activity
# WHY: Duration tells us which steps are bottlenecks.
df = df.sort_values(["case:concept:name", "time:timestamp"])
df["duration_seconds"] = (
    df.groupby("case:concept:name")["time:timestamp"].diff().dt.total_seconds().fillna(0)
).abs()

activity_durations = (
    df[~df["concept:name"].str.startswith("REWORK_", na=False)]
    .groupby("concept:name")["duration_seconds"]
    .agg(["mean", "median", "std", "count"])
)
activity_durations["mean_minutes"] = activity_durations["mean"] / 60.0
print("\n3. Average Duration per Activity (excluding rework):")
print(activity_durations.sort_values("mean_minutes", ascending=False).head(10))

# 5.4 Rework analysis
print("\n4. Rework Analysis:")
rework_events = df[df["concept:name"].str.startswith("REWORK_", na=False)]
if not rework_events.empty:
    print(rework_events["concept:name"].value_counts())
else:
    print("No rework events found.")

# -----------------------------------------
# 6) Conformance checking
# WHY: Validates if the real logs fit the discovered model.
# -----------------------------------------
print("\n5. Conformance Checking:")

try:
    _alignments = alignments_module.apply(event_log, petri_net, initial_marking, final_marking)
    print("  Alignments computed.")
except Exception as e:
    print(f"  Alignments skipped: {e}")

try:
    eval_results = eval_algorithm.apply(event_log, petri_net, initial_marking, final_marking)
    print("  Model Evaluation:")
    for metric, result in eval_results.items():
        if isinstance(result, dict) and "value" in result:
            print(f"    {metric.title()}: {result['value']:.4f}")
        elif isinstance(result, (int, float)):
            print(f"    {metric.title()}: {result:.4f}")
        else:
            print(f"    {metric.title()}: {result}")
except Exception as e:
    print(f"  Unified evaluation skipped: {e}")

# ----------------------------------------------------
# 7) Batch size vs performance analysis
# WHY: This connects process mining to manufacturing KPIs.
# - Batch size is the number of units produced together.
# - We want to know if bigger batches are faster/slower,
#   and whether they are more/less prone to rework.
# ----------------------------------------------------
print("\n6. Analysis of Batch Size and Process Duration:")

if "batch_size" in df.columns:
    # Case-level stats
    trace_durations_df = df.groupby("case:concept:name").agg(
        first_timestamp=("time:timestamp", "min"),
        last_timestamp=("time:timestamp", "max"),
        batch_size=("batch_size", lambda x: x.iloc[0]),
    )
    trace_durations_df["total_duration_minutes"] = (
        (trace_durations_df["last_timestamp"] - trace_durations_df["first_timestamp"]).dt.total_seconds() / 60.0
    )

    # Correlation: batch size vs total duration
    print("  Correlation between batch size and processing time:")
    print(trace_durations_df[["batch_size", "total_duration_minutes"]].corr())

    # Rework occurrence rate by batch size group
    df_with_batch = df.merge(trace_durations_df[["batch_size"]], left_on="case:concept:name", right_index=True)
    df_with_batch["batch_size_group"] = pd.cut(df_with_batch["batch_size_y"], bins=5, labels=False, include_lowest=True)
    rework_df = df_with_batch[df_with_batch["concept:name"].str.startswith("REWORK_", na=False)]
    if not rework_df.empty:
        # Define bins ONCE to ensure consistent categories
        bins = pd.interval_range(
            start=df_with_batch["batch_size_y"].min(),
            end=df_with_batch["batch_size_y"].max(),
            periods=5
        )
        df_with_batch["batch_size_group"] = pd.cut(df_with_batch["batch_size_y"], bins=bins, include_lowest=True)
        rework_df["batch_size_group"] = pd.cut(rework_df["batch_size_y"], bins=bins, include_lowest=True)

        # Count unique cases in each bin
        total_counts = df_with_batch.groupby("batch_size_group")["case:concept:name"].nunique()
        rework_counts = rework_df.groupby("batch_size_group")["case:concept:name"].nunique()

        # Compute % safely (fill missing bins with 0)
        rework_rate = (rework_counts / total_counts) * 100
        rework_rate = rework_rate.fillna(0).round(1)

        print("\n  Rework occurrence rate (%) by batch size group:")
        print(rework_rate)
else:
    print("  'batch_size' column not found in the event log. Skipping batch size analysis.")

# ----------------------------------------------------
# Optional: Quick visualization of rework vs batch size
# ----------------------------------------------------
try:
    import plotext as plt
except ImportError:
    plt = None
    print("Install 'plotext' if you want terminal-based ASCII charts (pip install plotext).")

# Only plot if rework_rate exists and is not empty
if 'rework_rate' in locals() and not rework_rate.empty:
    # Convert interval index into neat labels like "500–1400"
    clean_labels = [
        f"{int(interval.left)}–{int(interval.right)}"
        for interval in rework_rate.index
    ]

    y_values = rework_rate.values

    if plt is not None:
        print("\nRework Rate by Batch Size Group (ASCII chart):")
        plt.clear_figure()
        plt.plotsize(60, 15)  # width=60 chars, height=15 rows
        plt.bar(clean_labels, y_values)
        plt.title("Rework Rate by Batch Size Group")
        plt.ylabel("% Rework")
        plt.show()

print("\nDone.")

