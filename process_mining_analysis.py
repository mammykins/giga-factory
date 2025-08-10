import pm4py
from pm4py.algo.discovery.inductive import algorithm as inductive_miner
from pm4py.algo.conformance.alignments.petri_net.algorithm import Variants as Alignments
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.evaluation.replay_fitness.param import Parameters as ReplayFitnessParameters
from pm4py.evaluation.precision.param import Parameters as PrecisionParameters
from pm4py.evaluation.generalization.param import Parameters as GeneralizationParameters
from pm4py.evaluation.robustness.param import Parameters as RobustnessParameters
from pm4py.viz.petri_net import visualizer as pn_viz
from pm4py.statistics.attributes import common as attr_common
from pm4py.statistics.end_activities import common as end_activity_utils
from pm4py.statistics.start_activities import common as start_activity_utils
from pm4py.statistics.trace_stats import bootstrap as trace_stats_bootstrap
from pm4py.util.vis.common import save_vis

# --- Load the synthetic data ---
# If you didn't save it, uncomment the generation line:
# synthetic_log_df = generate_battery_production_log(num_cases=1000)

# Ensure the dataframe has the correct pm4py format (case_id, activity, timestamp)
# If you saved it, load it:
try:
    event_log_df = pd.read_csv("battery_production_event_log.csv")
    print("\nLoaded event log from CSV.")
except FileNotFoundError:
    print("CSV not found, generating synthetic data again.")
    event_log_df = generate_battery_production_log(num_cases=1000)
    event_log_df.to_csv("battery_production_event_log.csv", index=False)

# Convert pandas DataFrame to pm4py EventLog object
# Ensure your timestamp column is in datetime format
event_log_df['timestamp'] = pd.to_datetime(event_log_df['timestamp'])

# Map DataFrame columns to the expected EventLog structure
parameters = {
    log_converter.Variants.TO_EVENT_LOG.value.CASE_ID_KEY: "case_id",
    log_converter.Variants.TO_EVENT_LOG.value.ACTIVITY_KEY: "activity",
    log_converter.Variants.TO_EVENT_LOG.value.TIMESTAMP_KEY: "timestamp",
}

# Add optional attributes if they exist
if 'resource' in event_log_df.columns:
    parameters[log_converter.Variants.TO_EVENT_LOG.value.RESOURCE_KEY] = "resource"
if 'batch_size' in event_log_df.columns:
     # pm4py uses 'attributes' for extra columns. We need to make sure these are recognized.
     # For simplicity, let's focus on core attributes first, or explicitly add them.
     # A common way is to convert them to a dictionary of attributes.
     pass # We'll handle batch_size during analysis later

event_log = pm4py.convert_to_event_log(event_log_df, parameters=parameters)

print("\nPM4Py EventLog Created:")
print(event_log)

# --- Basic Process Discovery (Inductive Miner) ---
# This algorithm tries to discover a Petri Net model from the event log.
print("\nDiscovering Process Model (Inductive Miner)...")
petri_net, initial_marking, final_marking = inductive_miner.apply(event_log)

# Visualize the discovered Petri Net
print("Visualizing Process Model...")
try:
    # You can save the visualization to a file
    pn_viz.save(petri_net, initial_marking, final_marking, "discovered_process_model.png")
    print("Discovered process model saved to 'discovered_process_model.png'")

    # If you have graphviz installed and configured:
    # pn_viz.view(petri_net, initial_marking, final_marking)

except Exception as e:
    print(f"Could not visualize the Petri Net. Ensure graphviz is installed and in your PATH, or check the save path. Error: {e}")


# --- Extracting Insights from the Log ---

print("\n--- Key Process Insights ---")

# 1. Most Frequent Activities
print("\n1. Most Frequent Activities:")
activity_counts = event_log_df['activity'].value_counts()
print(activity_counts.head(10)) # Show top 10

# 2. Start and End Activities
print("\n2. Start and End Activities:")
start_activities = start_activity_utils.get_start_activities(event_log)
end_activities = end_activity_utils.get_end_activities(event_log)
print(f"  Start Activities: {start_activities}")
print(f"  End Activities: {end_activities}")

# 3. Bottleneck Analysis (Average duration per activity)
print("\n3. Average Duration per Activity:")
# We need to calculate duration for each event.
# For rework activities, we'll mark them differently or analyze them separately.
# Let's filter out 'REWORK_' activities for this average duration calculation
# to get the "normal" path duration.
event_log_df['duration_seconds'] = (event_log_df.groupby('case_id')['timestamp'].diff().dt.total_seconds().fillna(0)).abs()

# Exclude self-loops or initial timestamp diffs which are often 0
activity_durations = event_log_df[
    event_log_df['activity'].str.startswith("REWORK_") == False
].groupby('activity')['duration_seconds'].agg(['mean', 'median', 'std', 'count'])

activity_durations['mean_minutes'] = activity_durations['mean'] / 60
activity_durations['median_minutes'] = activity_durations['median'] / 60

print(activity_durations.sort_values(by='mean_minutes', ascending=False).head(10))

# Identify potential bottlenecks: activities with long average durations.
# "Assembly/Packaging" and "Storage (Raw Material)" often appear here.

# 4. Rework Analysis
print("\n4. Rework Analysis:")
rework_events = event_log_df[event_log_df['activity'].str.startswith("REWORK_")]
if not rework_events.empty:
    rework_counts = rework_events['activity'].value_counts()
    print(rework_counts)
    # We can see which activities are most frequently reworked.
    # From our data generation, we expect "REWORK_Quality Check (Raw Material)"
    # and "REWORK_In-Process Quality Check", "REWORK_Assembly/Packaging" etc.
else:
    print("No rework events found in the synthetic data.")

# 5. Conformance Checking (comparing log to model)
# This is more advanced. We'll use alignments to see how closely actual traces
# match the discovered model. A high number of "gaps" or "mismatches" in alignments
# indicates deviation from the "ideal" process.

print("\n5. Conformance Checking (Basic Alignment Fitness):")
# Get the alignment from the log using the discovered petri net
alignments = Alignments.apply(event_log, petri_net, initial_marking, final_marking)

# We can analyze the alignments for each trace
# For example, let's get the fitness score for each trace
trace_fitness = {}
for i, trace in enumerate(event_log):
    # Use the alignment for this trace (alignments is a list of alignments, one per trace)
    trace_alignment = alignments[i]
    # Calculate fitness for this trace (number of aligned moves / total moves in log trace)
    # pm4py also provides aggregate fitness scores.
    # Let's use pm4py's replay fitness calculation which is more direct.
    pass # The following fitness calculation is more standard

# Replay the log against the model to get fitness, precision, generalization, etc.
# Fitness: How well the log can be replayed by the model. High fitness means
# the model covers the observed behavior. Low fitness means there's behavior in the log
# not explained by the model (or the model is too strict).
print("  Calculating Replay Fitness...")
replay_fitness_params = ReplayFitnessParameters(
    return_aggregated_results=True,
    show_durations=False # Set to True if duration info is in the log attributes
)
fitness_results = pm4py.evaluate_replay_fitness(event_log, petri_net, initial_marking, final_marking, parameters=replay_fitness_params)
print(f"    Log Fitness: {fitness_results['fitness']:.4f}") # High is good

# Precision: How many steps in the model are actually used by the log. High precision means
# the model is precise and doesn't include unnecessary behavior.
print("  Calculating Precision...")
precision_params = PrecisionParameters(
    return_aggregated_results=True,
    show_durations=False
)
precision_results = pm4py.evaluate_precision(event_log, petri_net, initial_marking, final_marking, parameters=precision_params)
print(f"    Precision: {precision_results['precision']:.4f}") # High is good

# Generalization: How well the discovered model can represent unseen traces.
print("  Calculating Generalization...")
generalization_params = GeneralizationParameters(
    return_aggregated_results=True
)
# For generalization, you'd typically split your log into a training and test set.
# For this synthetic example, we'll skip actual splitting and just note the concept.
print("    (Skipping actual generalization test, requires log splitting)")

# Robustness: How resistant the model is to noise or variations.
print("  Calculating Robustness...")
robustness_params = RobustnessParameters(
    return_aggregated_results=True
)
robustness_results = pm4py.evaluate_robustness(event_log, petri_net, initial_marking, final_marking, parameters=robustness_params)
print(f"    Robustness: {robustness_results['robustness']:.4f}") # High is good


# 6. Analysis on Batch Size and Duration (using custom attributes)
# This requires accessing the 'batch_size' attribute for each trace or activity.
# pm4py stores attributes per trace or per event.
# For event-specific attributes like batch_size at each step, we might need to extract them manually.

print("\n6. Analysis of Batch Size and Process Duration:")

# Let's analyze how batch size might correlate with overall process duration.
# We'll group by case_id and find the total duration for each batch.
trace_durations_df = event_log_df.groupby('case_id').agg(
    first_timestamp=('timestamp', 'min'),
    last_timestamp=('timestamp', 'max'),
    batch_size=('batch_size', lambda x: x.iloc[0]) # Assuming batch_size is consistent per case
)
trace_durations_df['total_duration_seconds'] = (trace_durations_df['last_timestamp'] - trace_durations_df['first_timestamp']).dt.total_seconds()
trace_durations_df['total_duration_minutes'] = trace_durations_df['total_duration_seconds'] / 60

print("  Overall batch processing time vs. batch size:")
print(trace_durations_df[['batch_size', 'total_duration_minutes']].corr()) # Correlation coefficient

# Analyze duration of specific steps vs. batch size
# For this, we need to map batch_size to each event.
# We can merge the batch_size back to the main event_log_df
event_log_df_with_batch = event_log_df.merge(
    trace_durations_df[['batch_size']],
    left_on='case_id',
    right_index=True,
    how='left'
)

# Average duration of 'Assembly/Packaging' vs. batch size
assembly_df = event_log_df_with_batch[event_log_df_with_batch['activity'] == 'Assembly/Packaging']
if not assembly_df.empty:
    assembly_duration_vs_batch = assembly_df.groupby('batch_size')['duration_seconds'].mean()
    # For large numbers of batch sizes, it's better to bin them.
    assembly_df['batch_size_group'] = pd.cut(assembly_df['batch_size'], bins=5, labels=False, include_lowest=True)
    avg_assembly_duration_by_group = assembly_df.groupby('batch_size_group')['duration_seconds'].mean() / 60
    print("\n  Average Assembly/Packaging duration (minutes) by batch size group:")
    print(avg_assembly_duration_by_group)
    # This might show if larger batches take longer to assemble.

# Analyze rework rate by batch size (e.g., if larger batches are more prone to QC issues)
rework_events_with_batch = event_log_df_with_batch[event_log_df_with_batch['activity'].str.startswith("REWORK_")]
if not rework_events_with_batch.empty:
    rework_events_with_batch['batch_size_group'] = pd.cut(rework_events_with_batch['batch_size'], bins=5, labels=False, include_lowest=True)
    rework_rate_by_batch_group = rework_events_with_batch.groupby('batch_size_group')['case_id'].count()
    total_batches_in_group = event_log_df_with_batch.groupby('batch_size_group')['case_id'].nunique()

    # Avoid division by zero if a group has no batches
    rework_occurrence_rate = (rework_rate_by_batch_group / total_batches_in_group).fillna(0) * 100

    print("\n  Rework occurrence rate (%) by batch size group:")
    print(rework_occurrence_rate)
