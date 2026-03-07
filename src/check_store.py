#!/usr/bin/env python3
"""
Check Store Status
Shows what's currently in your File Search Store
"""
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

print("="*70)
print("  📊 FILE SEARCH STORE STATUS")
print("="*70)

# Create client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Load store name
with open("store_name.txt", "r") as f:
    store_name = f.read().strip()

print(f"\n📁 Store: {store_name}")

# Get all documents
docs = list(client.file_search_stores.documents.list(parent=store_name))

print(f"\n✅ Documents in store: {len(docs)}")

if len(docs) == 0:
    print("\n   (Store is empty)")
else:
    print("\nDocuments:")
    for i, doc in enumerate(docs, 1):
        print(f"\n   {i}. 📄 {doc.display_name}")
        print(f"      ID: {doc.name}")

print("\n" + "="*70)