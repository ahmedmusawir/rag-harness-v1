#!/usr/bin/env python3
"""
LESSON 1: Check if File Search API is available
Just checking - no uploading, no querying, just inspection
"""
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

print("LESSON 1: Checking File Search API Availability\n")

# Create client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Check if file_search_stores exists
print("Checking client attributes...")

if hasattr(client, 'file_search_stores'):
    print("✅ client.file_search_stores EXISTS!")
    
    print("\nWhat can we do with it?")
    methods = [m for m in dir(client.file_search_stores) if not m.startswith('_')]
    for method in methods:
        print(f"   - {method}")
    
    print("\n🎉 File Search API is available!")
    print("   We can create stores, upload files, and query them!")
else:
    print("❌ client.file_search_stores NOT FOUND")
    print("   Your SDK version might be too old")
    print("   Run: pip install --upgrade google-genai")

print("\n---")
print("What did we learn?")
print("- The File Search API is accessed via client.file_search_stores")
print("- It's separate from client.files (which is just basic file storage)")