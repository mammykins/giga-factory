#!/usr/bin/env python3
"""
Test script to verify that environment variables are loaded correctly from .env file.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve the NVIDIA API key
nvidia_api_key = os.getenv("NVIDIA_API_KEY")

# Print the result
if nvidia_api_key:
    # Mask the key for security (show first 8 chars only)
    masked_key = nvidia_api_key[:8] + "..." if len(nvidia_api_key) > 8 else "***"
    print(f"✓ NVIDIA_API_KEY loaded successfully: {masked_key}")
    print(f"  Full length: {len(nvidia_api_key)} characters")
else:
    print("✗ NVIDIA_API_KEY not found!")
    print("  Make sure you've set it in the .env file")
