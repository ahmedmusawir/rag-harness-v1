#!/usr/bin/env python3
"""
Test Gemini model access
"""
from google import genai

client = genai.Client(
    vertexai=True,
    project="ninth-potion-455712-g9",
    location="us-central1"
    # location="us-east1"
)

print("🧪 Testing Gemini models...\n")

# Test different Gemini models
models_to_test = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    # "gemini-3-pro-preview",
]

for model_name in models_to_test:
    try:
        print(f"Testing: {model_name}... ", end="")
        response = client.models.generate_content(
            model=model_name,
            contents="Say 'Hello Tony!' in one sentence."
        )
        print(f"✅ Works! Response: {response.text.strip()}")
    except Exception as e:
        print(f"❌ Failed: {e}")

print("\n✅ Gemini access confirmed!")