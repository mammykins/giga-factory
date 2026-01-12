import os
import requests
from dotenv import load_dotenv, find_dotenv

# Load env vars
load_dotenv(find_dotenv())

api_key = os.getenv("NVIDIA_API_KEY")
model_id = "nvidia/nemotron-3-nano-30b-a3b"
print(f"🔑 Testing Key: {api_key[:10]}...")

if not api_key or not api_key.startswith("nvapi-"):
    print("⚠️  WARNING: Key does not start with 'nvapi-'. It will likely fail.")

response = requests.post(
    "https://integrate.api.nvidia.com/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": model_id,
        "messages": [{"role": "user", "content": "Say hello!"}],
        "temperature": 0.5,
        "max_tokens": 10,
    },
)

if response.status_code == 200:
    print("✅ SUCCESS! The key works and the model is available.")
else:
    print(f"❌ FAILED with code {response.status_code}")
    print(f"Reason: {response.text}")
