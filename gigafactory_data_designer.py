import os
import sys
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv, find_dotenv

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


# 1. Define Polymorphic Schema
# Instead of hardcoding "Voltage", we define a generic measurement structure.
# This allows the LLM to dynamically decide that "Mixing" needs "Viscosity"
# and "Formation" needs "Voltage".
class ProcessMeasurement(BaseModel):
    metric_name: str = Field(
        description="The technical name of the measurement (e.g., 'Slurry Viscosity', 'Electrode Thickness', 'OCV Voltage')"
    )
    value: float = Field(description="The numeric value of the measurement")
    unit: str = Field(description="The unit of measure (e.g., 'Pa.s', 'microns', 'V', 'mOhm')")
    status: Literal["In Spec", "Tolerance Warning", "Critical Fail"] = Field(
        description="The quality assessment based on the value"
    )


def main():
    # Load environment variables. find_dotenv() helps if .env is in a parent directory.
    load_dotenv(find_dotenv())
    
    nvidia_api_key = os.getenv("NVIDIA_API_KEY")
    
    # Check for the key immediately to avoid confusing "health check" errors later
    if not nvidia_api_key:
        print("\n❌ ERROR: NVIDIA_API_KEY not found in environment.")
        print("   Please check that your .env file exists and contains NVIDIA_API_KEY=nvapi-...")
        sys.exit(1)
    
    print(f"✅ API Key loaded (starts with {nvidia_api_key[:10]}...)")

    data_designer = DataDesigner()

    # 2. Configure the Model
    MODEL_ALIAS = "nemotron-nano-v3"
    MODEL_ID = "nvidia/nemotron-3-nano-30b-a3b"
    
    # We apply the specific configuration from your working script.
    # The 'extra_body' parameter disables the 'thinking' output feature.
    # Without this, the API gateway for this specific model often returns 
    # errors that look like authentication failures during health checks.
    model_configs = [
        ModelConfig(
            alias=MODEL_ALIAS,
            model=MODEL_ID,
            provider="nvidia",
            inference_parameters=ChatCompletionInferenceParams(
                temperature=0.4,  # Lower temperature for more consistent technical metrics
                max_tokens=1024,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            ),
        )
    ]

    config_builder = DataDesignerConfigBuilder(model_configs=model_configs)

    # 3. Add Core Samplers for Factory Operations
    print("🛠️  Configuring factory simulation columns...")
    
    # Unique Traceability
    config_builder.add_column(
        SamplerColumnConfig(
            name="case_id",
            sampler_type=SamplerType.UUID,
            params=UUIDSamplerParams(prefix="BATCH-", short_form=True, uppercase=True),
        )
    )

    # Hierarchical Activity Logic
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

    # 4. Add Domain-Grounded UK Staffing
    # We drop this column from the final dataset, but keep it available
    # for the ExpressionColumnConfig below to use as context.
    config_builder.add_column(
        SamplerColumnConfig(
            name="operator_data",
            sampler_type=SamplerType.PERSON_FROM_FAKER,
            params=PersonFromFakerSamplerParams(locale="en_GB", age_range=[18, 65]),
            drop=True, 
        )
    )

    # Combine data from the dropped column into a formatted string
    config_builder.add_column(
        ExpressionColumnConfig(
            name="resource",
            expr="{{ operator_data.first_name }} {{ operator_data.last_name }} ({{ operator_data.occupation }})",
        )
    )

    # 5. Add Environmental Measurements
    config_builder.add_column(
        SamplerColumnConfig(
            name="ambient_temp_c",
            sampler_type=SamplerType.GAUSSIAN,
            params=GaussianSamplerParams(mean=21.5, stddev=1.2, decimal_places=2),
        )
    )

    # 6. Generate Narrative Logs (Connecting the Data)
    # The prompt references the structured data we generate (qc_data),
    # ensuring the text matches the numbers.
    config_builder.add_column(
        LLMTextColumnConfig(
            name="operator_log",
            model_alias=MODEL_ALIAS,
            prompt="""Write a short, telegraphic operator log for batch {{ case_id }} at step {{ subcategory }}.
            
            The system recorded a value of {{ qc_data.value }} {{ qc_data.unit }} for {{ qc_data.metric_name }}.
            The status was flagged as: {{ qc_data.status }}.
            
            If the status is 'In Spec', simply note 'Process nominal'.
            If 'Tolerance Warning' or 'Critical Fail', describe a potential root cause (e.g., 'pump pressure fluctuation', 'oven temp drift', 'debris on sensor').""",
        )
    )

    # 7. Contextual Quality Metrics (The Logic Upgrade)
    # We ask the LLM to look at 'subcategory' and pick the scientifically correct metric.
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

    # 8. Validate and Preview
    print("🚦 Validating configuration...")
    data_designer.validate(config_builder)
    
    print("🚀 Generating preview (performing health checks)...")
    try:
        preview = data_designer.preview(config_builder, num_records=5)
        print("\n" + "="*80)
        preview.display_sample_record()
        print("="*80)
        
        # Optional: Print a clean summary table to verify the "Context" logic worked
        print("\n🔍 Contextual Verification (First 5 rows):")
        df = preview.dataset
        # Display key columns to verify polymorphic metrics
        print(df[['subcategory', 'qc_data']].to_string())
        
        print("\n✅ Success!")
    except Exception as e:
        print(f"\n❌ Generation failed. Error details:\n{e}")

if __name__ == "__main__":
    main()
