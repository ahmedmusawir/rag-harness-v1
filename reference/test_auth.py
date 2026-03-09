#!/usr/bin/env python3
"""
Test Vertex AI authentication
Run from project root: python src/test_auth.py
"""
from google import genai

print("🔍 Testing Vertex AI connection...")

client = genai.Client(
    vertexai=True,
    project="ninth-potion-455712-g9",
    location="us-east1"
)

try:
    models = list(client.models.list())
    print("✅ Authentication successful!")
    print(f"✅ Found {len(models)} models available\n")
    
    # Show ALL models
    print("📋 All available models:")
    for i, model in enumerate(models, 1):
        print(f"   {i}. {model.name}")
        
except Exception as e:
    print(f"❌ Error: {e}")