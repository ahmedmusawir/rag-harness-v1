#!/usr/bin/env python3
"""
LESSON 2: Create a File Search Store
A store is like a "knowledge base" - a container for documents
Think of it like creating a folder before adding files
"""
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

print("LESSON 2: Creating a File Search Store\n")

# Create client with API key
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Step 1: Creating a store...")
print("   (This is like creating a folder/database)")

# Create the store
store = client.file_search_stores.create(
    config={'display_name': 'Tony-Test-Store'}
)

print("✅ Store created!\n")

print("What did we get back?")
print(f"   Store Name (ID): {store.name}")
print(f"   Display Name: {store.display_name}")

# Save the store name for next lesson
with open("store_name.txt", "w") as f:
    f.write(store.name)

print(f"\n💾 Saved store name to: store_name.txt")

print("\n---")
print("What did we learn?")
print("- A 'store' is a container for documents")
print("- Each store has a unique ID (store.name)")
print("- Display name is just for humans to read")
print("- The store is EMPTY right now (no files yet)")
print("\n📊 Storage used: 0 bytes (store is empty)")
print("💰 Cost so far: $0 (just created container)")