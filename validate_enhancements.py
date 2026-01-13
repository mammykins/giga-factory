"""
Validation script for gigafactory data enhancements:
1. Correlation: Friday_PM + Coating_Room should show elevated temperature
2. Batch Traceability: Batch IDs should repeat across multiple process steps
"""

import pandas as pd
import sys
from pathlib import Path

def validate_correlation(df):
    """Validate temperature correlation with shift and location."""
    print("\\n" + "="*80)
    print("TEST 1: Temperature Correlation (Bad Shift Signal)")
    print("="*80)
    
    bad_shift = df[(df['shift'] == 'Friday_PM') & (df['location'] == 'Coating_Room')]
    normal = df[~((df['shift'] == 'Friday_PM') & (df['location'] == 'Coating_Room'))]
    
    if len(bad_shift) == 0:
        print("⚠️  WARNING: No Friday_PM + Coating_Room records found in dataset")
        return False
    
    bad_mean = bad_shift['ambient_temp_c'].mean()
    normal_mean = normal['ambient_temp_c'].mean()
    temp_diff = bad_mean - normal_mean
    
    print(f"\\nBad Shift (Friday_PM + Coating_Room):")
    print(f"  Records: {len(bad_shift)}")
    print(f"  Mean Temperature: {bad_mean:.2f}°C")
    
    print(f"\\nNormal Conditions:")
    print(f"  Records: {len(normal)}")
    print(f"  Mean Temperature: {normal_mean:.2f}°C")
    
    print(f"\\nTemperature Difference: {temp_diff:.2f}°C")
    
    # Expected: ~5°C increase
    if temp_diff > 3.0:
        print("✅ PASS: Significant temperature increase detected (>3°C)")
        return True
    else:
        print(f"❌ FAIL: Temperature increase too small ({temp_diff:.2f}°C < 3°C)")
        return False

def validate_traceability(df):
    """Validate batch traceability across process steps."""
    print("\\n" + "="*80)
    print("TEST 2: Batch Traceability (Golden Thread)")
    print("="*80)
    
    batch_counts = df['case_id'].value_counts()
    
    print(f"\\nTotal records: {len(df)}")
    print(f"Unique batches: {len(batch_counts)}")
    print(f"Records per batch (avg): {batch_counts.mean():.2f}")
    print(f"Records per batch (min): {batch_counts.min()}")
    print(f"Records per batch (max): {batch_counts.max()}")
    
    # Check if batches repeat (traceability)
    multi_step_batches = batch_counts[batch_counts > 1]
    print(f"\\nBatches with multiple records: {len(multi_step_batches)} / {len(batch_counts)}")
    
    # Show example batch flow
    if len(multi_step_batches) > 0:
        example_batch = multi_step_batches.index[0]
        example_records = df[df['case_id'] == example_batch][['case_id', 'process_step', 'subcategory']].sort_values('process_step')
        print(f"\\nExample batch flow ({example_batch}):")
        print(example_records.to_string(index=False))
    
    # Check for logical step progression
    print(f"\\nProcess step distribution:")
    print(df['process_step'].value_counts().sort_index().to_string())
    
    # Check subcategory-to-step mapping
    print(f"\\nSubcategory-to-step mapping validation:")
    step_mapping = df.groupby('process_step')['subcategory'].unique()
    for step, subcats in step_mapping.items():
        print(f"  Step {step}: {', '.join(subcats)}")
    
    # Expected: Most batches should have multiple steps
    success_rate = len(multi_step_batches) / len(batch_counts)
    print(f"\\nTraceability Success Rate: {success_rate*100:.1f}%")
    
    if success_rate > 0.5:
        print("✅ PASS: Majority of batches tracked across multiple steps")
        return True
    else:
        print(f"❌ FAIL: Too few batches with traceability ({success_rate*100:.1f}% < 50%)")
        return False

def main():
    # Check if CSV file exists (from previous run)
    csv_path = Path("gigafactory_synthetic_data.csv")
    
    if not csv_path.exists():
        print("❌ ERROR: No data file found. Please run gigafactory_data_designer.py first")
        print("   and save the dataset with:")
        print("   preview.dataset.to_csv('gigafactory_synthetic_data.csv', index=False)")
        sys.exit(1)
    
    # Load data
    print("Loading data from gigafactory_synthetic_data.csv...")
    df = pd.read_csv(csv_path)
    
    print(f"\\nDataset shape: {df.shape[0]} records × {df.shape[1]} columns")
    print(f"Columns: {', '.join(df.columns.tolist())}")
    
    # Run validations
    test1_pass = validate_correlation(df)
    test2_pass = validate_traceability(df)
    
    # Summary
    print("\\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    print(f"Test 1 (Correlation): {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"Test 2 (Traceability): {'✅ PASS' if test2_pass else '❌ FAIL'}")
    
    if test1_pass and test2_pass:
        print("\\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\\n⚠️  Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
