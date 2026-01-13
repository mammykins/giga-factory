"""
Test script to validate the polymorphic schema implementation.
Generates a larger dataset and validates:
1. Metric diversity across subcategories
2. Status distribution (~90% In Spec)
3. Context-appropriate metrics
"""

import os
import sys
from collections import Counter
from dotenv import load_dotenv, find_dotenv

# Import from the main script
from gigafactory_data_designer import ProcessMeasurement

from data_designer.essentials import (
    CategorySamplerParams,
    ChatCompletionInferenceParams,
    DataDesigner,
    DataDesignerConfigBuilder,
    LLMTextColumnConfig,
    LLMStructuredColumnConfig,
    ModelConfig,
    PersonFromFakerSamplerParams,
    SamplerColumnConfig,
    SamplerType,
    SubcategorySamplerParams,
    GaussianSamplerParams,
    UUIDSamplerParams,
    ExpressionColumnConfig,
)


def main():
    load_dotenv(find_dotenv())
    
    nvidia_api_key = os.getenv("NVIDIA_API_KEY")
    if not nvidia_api_key or not nvidia_api_key.startswith("nvapi-"):
        print("\n❌ ERROR: Invalid or missing NVIDIA_API_KEY")
        sys.exit(1)

    data_designer = DataDesigner()

    # Configure the model
    MODEL_ALIAS = "nemotron-nano-v3"
    model_configs = [
        ModelConfig(
            alias=MODEL_ALIAS,
            model="nvidia/nemotron-3-nano-30b-a3b",
            provider="nvidia",
            inference_parameters=ChatCompletionInferenceParams(
                temperature=0.4,
                max_tokens=1024,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            ),
        )
    ]

    config_builder = DataDesignerConfigBuilder(model_configs=model_configs)

    print("🧪 Generating validation dataset (20 records)...")

    # Add columns (same as main script but simplified)
    config_builder.add_column(
        SamplerColumnConfig(
            name="case_id",
            sampler_type=SamplerType.UUID,
            params=UUIDSamplerParams(prefix="BATCH-", short_form=True, uppercase=True),
        )
    )

    config_builder.add_column(
        SamplerColumnConfig(
            name="activity",
            sampler_type=SamplerType.CATEGORY,
            params=CategorySamplerParams(
                values=["Electrode Manufacturing", "Cell Assembly", "Formation & Aging"]
            ),
        )
    )

    config_builder.add_column(
        SamplerColumnConfig(
            name="subcategory",
            sampler_type=SamplerType.SUBCATEGORY,
            params=SubcategorySamplerParams(
                category="activity",
                values={
                    "Electrode Manufacturing": [
                        "Slurry Mixing",
                        "Coating & Drying",
                        "Calendering",
                    ],
                    "Cell Assembly": [
                        "Winding/Stacking",
                        "Electrolyte Filling",
                        "Cap Welding",
                    ],
                    "Formation & Aging": [
                        "Initial Charging",
                        "High-Temp Aging",
                        "Final Grading",
                    ],
                },
            ),
        )
    )

    # Add the polymorphic quality metrics column
    config_builder.add_column(
        LLMStructuredColumnConfig(
            name="qc_data",
            model_alias=MODEL_ALIAS,
            output_format=ProcessMeasurement,
            prompt="""You are a QA Lead at a Battery Gigafactory.
            Generate a realistic quality measurement for the step: '{{ subcategory }}'.
            
            Follow these physics rules:
            - If 'Slurry Mixing': Measure Viscosity (target 3000-5000 Pa.s) or Solid Content (%).
            - If 'Coating & Drying': Measure Electrode Thickness (target 120-150 microns) or Loading Level.
            - If 'Calendering': Measure Density (target 2.5-3.0 g/cm³) or Thickness Uniformity.
            - If 'Winding/Stacking': Measure Alignment Precision (target <0.5 mm) or Layer Count.
            - If 'Electrolyte Filling': Measure Electrolyte Weight (g) or Wetting Percentage.
            - If 'Cap Welding': Measure Weld Depth (mm) or Tensile Strength (N).
            - If 'Initial Charging': Measure Voltage (V) or Current (A).
            - If 'High-Temp Aging': Measure Voltage Drop (K-value) or Capacity Fade (%).
            - If 'Final Grading': Measure Internal Resistance (target 1.5-3.0 mOhm) or Capacity (Ah).
            
            Simulate a realistic distribution where 90% are 'In Spec'.""",
        )
    )

    # Generate larger dataset using preview
    data_designer.validate(config_builder)
    result = data_designer.preview(config_builder, num_records=20)
    dataset = result.dataset
    
    print("\n" + "="*80)
    print("📊 VALIDATION RESULTS")
    print("="*80)
    
    # Extract data for analysis
    subcategories = dataset['subcategory']
    qc_data = dataset['qc_data']
    
    # 1. Check metric diversity by subcategory
    print("\n✅ TEST 1: Metric Diversity by Subcategory")
    print("-" * 80)
    subcategory_metrics = {}
    for i, subcat in enumerate(subcategories):
        metric_name = qc_data[i]['metric_name']
        unit = qc_data[i]['unit']
        if subcat not in subcategory_metrics:
            subcategory_metrics[subcat] = []
        subcategory_metrics[subcat].append(f"{metric_name} ({unit})")
    
    for subcat, metrics in sorted(subcategory_metrics.items()):
        unique_metrics = set(metrics)
        print(f"  {subcat:25} → {', '.join(unique_metrics)}")
    
    # 2. Check status distribution
    print("\n✅ TEST 2: Status Distribution")
    print("-" * 80)
    statuses = [qc['status'] for qc in qc_data]
    status_counts = Counter(statuses)
    total = len(statuses)
    for status, count in status_counts.items():
        percentage = (count / total) * 100
        print(f"  {status:20} → {count:3} records ({percentage:.1f}%)")
    
    in_spec_percentage = (status_counts.get('In Spec', 0) / total) * 100
    if in_spec_percentage >= 85:
        print(f"\n  ✅ PASS: {in_spec_percentage:.1f}% 'In Spec' (target: ~90%)")
    else:
        print(f"\n  ⚠️  WARNING: {in_spec_percentage:.1f}% 'In Spec' (target: ~90%)")
    
    # 3. Validate context-appropriate metrics
    print("\n✅ TEST 3: Context-Appropriate Metrics Validation")
    print("-" * 80)
    
    validation_rules = {
        "Slurry Mixing": ["Pa.s", "%"],  # Viscosity or Solid Content
        "Coating & Drying": ["microns", "micron"],  # Thickness
        "Calendering": ["g/cm³", "g/cm", "%"],  # Density
        "Winding/Stacking": ["mm"],  # Alignment
        "Electrolyte Filling": ["g", "%"],  # Weight or Wetting
        "Cap Welding": ["mm", "N"],  # Depth or Strength
        "Initial Charging": ["V", "A"],  # Voltage or Current
        "High-Temp Aging": ["K-value", "%", "V"],  # K-value or Fade
        "Final Grading": ["mOhm", "Ah"],  # Resistance or Capacity
    }
    
    validation_passed = True
    for i, subcat in enumerate(subcategories):
        unit = qc_data[i]['unit']
        expected_units = validation_rules.get(subcat, [])
        if not any(exp_unit in unit for exp_unit in expected_units):
            print(f"  ❌ FAIL: {subcat} has unexpected unit '{unit}' (expected: {expected_units})")
            validation_passed = False
    
    if validation_passed:
        print("  ✅ PASS: All metrics are context-appropriate!")
    
    # 4. Sample records display
    print("\n✅ TEST 4: Sample Records")
    print("-" * 80)
    for i in range(min(5, len(subcategories))):
        print(f"\n  Record {i+1}:")
        print(f"    Subcategory: {subcategories[i]}")
        print(f"    Metric: {qc_data[i]['metric_name']}")
        print(f"    Value: {qc_data[i]['value']} {qc_data[i]['unit']}")
        print(f"    Status: {qc_data[i]['status']}")
    
    print("\n" + "="*80)
    print("🎉 Validation Complete!")
    print("="*80)


if __name__ == "__main__":
    main()
