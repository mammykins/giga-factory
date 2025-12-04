# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a **process mining analysis framework** for gigafactory battery production. It generates synthetic battery manufacturing event logs and applies process mining techniques to discover workflows, identify bottlenecks, detect rework loops, and analyze batch performance.

### Key Technologies
- Python 3.13.5
- PM4Py (process mining library)
- Pandas/NumPy (data manipulation)
- Matplotlib (visualization)
- Graphviz (required for Petri net diagrams)

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Install Graphviz (required for visualizations)
brew install graphviz  # macOS
```

### Running the Analysis
```bash
# Step 1: Generate synthetic event log data
python battery_production_miner.py

# Step 2: Run process mining analysis
python process_mining_analysis.py
```

The workflow is **sequential**: `battery_production_miner.py` must run first to generate `battery_production_event_log.csv`, which is then consumed by `process_mining_analysis.py`.

### Testing
No formal test suite currently exists. Manual verification involves:
1. Checking that `battery_production_event_log.csv` is generated with expected structure
2. Verifying `discovered_process_model.png` is created
3. Reviewing console output for process insights

## Architecture

### Two-Stage Pipeline

**Stage 1: Data Generation** (`battery_production_miner.py`)
- Generates synthetic event logs simulating battery production
- Creates realistic process flow with configurable activities, durations, and rework probabilities
- Outputs CSV with columns: `case_id`, `activity`, `timestamp`, `resource`, `batch_size`
- Each case represents a production batch (e.g., `BATCH_00001`)

**Stage 2: Process Mining** (`process_mining_analysis.py`)
- Converts CSV to PM4Py EventLog format (XES-compliant naming)
- Discovers process model using **Inductive Miner** algorithm
- Converts process tree to **Petri Net** for formal analysis
- Performs conformance checking to validate model fitness
- Analyzes bottlenecks, rework patterns, and batch size correlations

### Key Process Flow
The synthetic production process simulates this logical flow:
1. Raw Material Arrival → Quality Check → Storage
2. Material Allocation → Production Batch Start
3. In-Process Quality Check → Assembly/Packaging → Final Quality Check
4. Storage (Finished Goods) → Order Fulfillment → Shipment

**Rework loops** are modeled by `REWORK_*` activity events that send batches back to previous stages.

### Data Model
- **Case ID**: Unique batch identifier (`BATCH_XXXXX`)
- **Activity**: Process step name (or `REWORK_<activity>` for rework events)
- **Timestamp**: When activity occurred
- **Resource**: Who/what performed the activity (Worker A/B, Machine X/Y, etc.)
- **Batch Size**: Number of units in the batch (500-5000)

## Code Patterns

### Synthetic Data Generation
- `generate_battery_production_log()` uses a `logical_flow` list to define the sequence of activities
- Each activity has configurable `duration`, `chance` (probability of occurrence), and `rework_to` (target for rework loops)
- Rework probability is set at 15% when applicable
- Uses `timedelta` to simulate realistic time progressions

### Process Mining Analysis
- **XES Column Mapping**: Renames DataFrame columns to PM4Py's expected format:
  - `case_id` → `case:concept:name`
  - `activity` → `concept:name`
  - `timestamp` → `time:timestamp`
- **Model Discovery**: Uses Inductive Miner variant `IMf` for flexibility with complex process trees
- **Duration Calculation**: Computes activity durations by taking timestamp diffs within each case
- **Batch Analysis**: Correlates batch size with total processing time and rework rates using pandas groupby operations

### Rework Detection
Rework events are identified by:
- Activity names starting with `REWORK_` prefix
- Filtered using `df["concept:name"].str.startswith("REWORK_", na=False)`
- Analyzed separately from normal activities to measure quality issues

## Output Files

- `battery_production_event_log.csv`: Generated synthetic event log (input to analysis)
- `discovered_process_model.png`: Petri net visualization of discovered process model
- Console output provides:
  - Most frequent activities
  - Start/end activities
  - Average activity durations (bottleneck identification)
  - Rework analysis
  - Conformance metrics (fitness, precision)
  - Batch size correlation with performance

## Important Notes

### Working with Real Data
To use real manufacturing data instead of synthetic:
1. Format your data as CSV with columns: `case_id`, `activity`, `timestamp`, `resource`, `batch_size`
2. Replace `battery_production_event_log.csv` with your real data file
3. Skip running `battery_production_miner.py` and directly run `process_mining_analysis.py`
4. Ensure timestamps are in a format parseable by `pd.to_datetime()`

### Dependencies on External Tools
- **Graphviz must be installed system-wide** (not just via pip) for Petri net visualization
- Without Graphviz, the script will skip visualization but continue with analysis
- `plotext` is optional for ASCII terminal charts; analysis works without it

### Process Mining Concepts
- **Petri Net**: Formal model showing places (circles), transitions (boxes), and flow of tokens
- **Inductive Miner**: Algorithm that discovers process models from event logs, handles noise well
- **Conformance Checking**: Validates how well real event logs match the discovered model
- **Fitness**: How much of the log can the model reproduce
- **Precision**: How much extra behavior does the model allow

## Extending the Project

### Adding New Activities
Edit `activities` dict in `battery_production_miner.py`:
```python
activities = {
    "New Activity Name": {
        "duration": (min_minutes, max_minutes),
        "chance": probability_0_to_1,
        "rework_to": "Target Activity or None"
    }
}
```
Then update `logical_flow` list to position it in the sequence.

### Modifying Analysis
In `process_mining_analysis.py`:
- Try different process discovery algorithms from `pm4py.algo.discovery`
- Add custom metrics by grouping/aggregating the DataFrame
- Export variants/traces using `pm4py.statistics.variants`
- Apply filters using `pm4py.filtering` module
