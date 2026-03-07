#!/usr/bin/env python3
"""
BONUS: Verify our store exists and check what's in it
"""
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("🔍 Checking our File Search Stores...\n")

# List ALL your stores
print("All stores in your account:")
stores = list(client.file_search_stores.list())
print(f"   Total stores: {len(stores)}")

for store in stores:
    print(f"\n   📁 {store.display_name}")
    print(f"      ID: {store.name}")
    
    # Check documents in this store
    try:
        docs = list(client.file_search_stores.documents.list(
            file_search_store_name=store.name
        ))
        print(f"      Documents: {len(docs)}")
    except:
        print(f"      Documents: 0 (empty)")

print("\n✅ Verification complete!")