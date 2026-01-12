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
    UniformSamplerParams,
    GaussianSamplerParams,
    UUIDSamplerParams,
    ExpressionColumnConfig,
)


# 1. Define Structured Output Schemas
class QualityMetric(BaseModel):
    internal_resistance_mohm: Decimal = Field(
        description="Measured internal resistance in milliohms", ge=1.0, le=5.0
    )
    voltage_v: Decimal = Field(description="Open circuit voltage", ge=3.2, le=4.2)
    pass_fail_status: Literal["Pass", "Marginal", "Fail"] = Field(
        description="Quality assessment result"
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
                temperature=0.7,
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

    # 6. Generate "Interesting" Narrative Insights
    config_builder.add_column(
        LLMTextColumnConfig(
            name="maintenance_log",
            model_alias=MODEL_ALIAS,
            prompt="""You are a factory floor supervisor at a UK battery giga-factory. 
            Describe a brief observation for the {{ subcategory }} step in batch {{ case_id }}. 
            Mention the ambient temperature of {{ ambient_temp_c }}°C. 
            If the temp is over 22°C, mention a slight cooling adjustment. 
            Keep it professional and technical.""",
        )
    )

    # 7. Structured Technical Data
    config_builder.add_column(
        LLMStructuredColumnConfig(
            name="quality_metrics",
            model_alias=MODEL_ALIAS,
            output_format=QualityMetric,
            prompt="Generate realistic battery quality metrics for the {{ subcategory }} process.",
        )
    )

    # 8. Validate and Preview
    print("🚦 Validating configuration...")
    data_designer.validate(config_builder)
    
    print("🚀 Generating preview (performing health checks)...")
    try:
        preview = data_designer.preview(config_builder, num_records=3)
        print("\n--- Sample Record ---")
        preview.display_sample_record()
        print("\n✅ Success!")
    except Exception as e:
        print(f"\n❌ Generation failed. Error details:\n{e}")

if __name__ == "__main__":
    main()
