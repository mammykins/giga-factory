#!/usr/bin/env python3
"""
Test script for data designer
"""

import os
from dotenv import load_dotenv

from data_designer.essentials import (
    CategorySamplerParams,
    ChatCompletionInferenceParams,
    DataDesigner,
    DataDesignerConfigBuilder,
    LLMTextColumnConfig,
    ModelConfig,
    PersonFromFakerSamplerParams,
    SamplerColumnConfig,
    SamplerType,
    SubcategorySamplerParams,
    UniformSamplerParams,
)


def main():
    # Load environment variables from .env file
    load_dotenv()

    # Retrieve the NVIDIA API key
    nvidia_api_key = os.getenv("NVIDIA_API_KEY")

    # When initialised without arguments the default model providers are used.
    data_designer = DataDesigner()

    # This name is set in the model provider configuration.
    MODEL_PROVIDER = "nvidia"

    # The model ID is from build.nvidia.com.
    MODEL_ID = "nvidia/nemotron-3-nano-30b-a3b"

    # We choose this alias to be descriptive for our use case.
    MODEL_ALIAS = "nemotron-nano-v3"

    model_configs = [
        ModelConfig(
            alias=MODEL_ALIAS,
            model=MODEL_ID,
            provider=MODEL_PROVIDER,
            inference_parameters=ChatCompletionInferenceParams(
                temperature=1.0,
                top_p=1.0,
                max_tokens=2048,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            ),
        )
    ]

    config_builder = DataDesignerConfigBuilder(model_configs=model_configs)

    # Let's start by designing a giga-factory battery production dataset
    config_builder.add_column(
        SamplerColumnConfig(
            name="product_category",
            sampler_type=SamplerType.CATEGORY,
            params=CategorySamplerParams(
                values=[
                    "Electronics",
                    "Clothing",
                    "Home & Kitchen",
                    "Books",
                    "Home Office",
                ],
            ),
        )
    )

    config_builder.add_column(
        SamplerColumnConfig(
            name="product_subcategory",
            sampler_type=SamplerType.SUBCATEGORY,
            params=SubcategorySamplerParams(
                category="product_category",
                values={
                    "Electronics": [
                        "Smartphones",
                        "Laptops",
                        "Headphones",
                        "Cameras",
                        "Accessories",
                    ],
                    "Clothing": [
                        "Men's Clothing",
                        "Women's Clothing",
                        "Winter Coats",
                        "Activewear",
                        "Accessories",
                    ],
                    "Home & Kitchen": [
                        "Appliances",
                        "Cookware",
                        "Furniture",
                        "Decor",
                        "Organization",
                    ],
                    "Books": [
                        "Fiction",
                        "Non-Fiction",
                        "Self-Help",
                        "Textbooks",
                        "Classics",
                    ],
                    "Home Office": [
                        "Desks",
                        "Chairs",
                        "Storage",
                        "Office Supplies",
                        "Lighting",
                    ],
                },
            ),
        )
    )

    config_builder.add_column(
        SamplerColumnConfig(
            name="target_age_range",
            sampler_type=SamplerType.CATEGORY,
            params=CategorySamplerParams(
                values=["18-25", "25-35", "35-50", "50-65", "65+"]
            ),
        )
    )

    # Optionally validate that the columns are configured correctly.
    data_designer.validate(config_builder)

    # We add samplers to generate data
    #
    config_builder.add_column(
        SamplerColumnConfig(
            name="customer",
            sampler_type=SamplerType.PERSON_FROM_FAKER,
            params=PersonFromFakerSamplerParams(age_range=[18, 70], locale="en_US"),
        )
    )

    config_builder.add_column(
        SamplerColumnConfig(
            name="number_of_stars",
            sampler_type=SamplerType.UNIFORM,
            params=UniformSamplerParams(low=1, high=5),
            convert_to="int",  # Convert the sampled float to an integer.
        )
    )

    config_builder.add_column(
        SamplerColumnConfig(
            name="review_style",
            sampler_type=SamplerType.CATEGORY,
            params=CategorySamplerParams(
                values=[
                    "rambling",
                    "brief",
                    "detailed",
                    "structured with bullet points",
                ],
                weights=[1, 2, 2, 1],
            ),
        )
    )

    data_designer.validate(config_builder)

    # preview data until satisfied
    #
    preview = data_designer.preview(config_builder, num_records=2)


if __name__ == "__main__":
    main()
