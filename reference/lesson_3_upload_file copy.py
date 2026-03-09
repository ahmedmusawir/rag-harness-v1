#!/usr/bin/env python3
"""
LESSON 3: Upload a File to File Search Store
Uses YOUR real files from /docs folder
"""
from google import genai
from dotenv import load_dotenv
from pathlib import Path
import os
import time
import sys

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))
from utils.cost_calculator import print_cost_estimate

load_dotenv()

print("LESSON 3: Upload a File to Store\n")

# Create client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Load our store from lesson 2
with open("store_name.txt", "r") as f:
    store_name = f.read().strip()

print(f"📁 Using store: {store_name}\n")

# Step 1: List available files in /docs
print("Step 1: Select a file to upload...")

docs_dir = Path("docs")
if not docs_dir.exists():
    print("❌ /docs folder doesn't exist!")
    print("   Create it and add some .txt or .pdf files")
    sys.exit(1)

# Get all text/pdf files
files = list(docs_dir.glob("*.txt")) + list(docs_dir.glob("*.pdf"))

if not files:
    print("❌ No .txt or .pdf files found in /docs!")
    print("   Add some files first")
    sys.exit(1)

print("Available files:")
for i, f in enumerate(files, 1):
    print(f"   {i}. {f.name} ({f.stat().st_size:,} bytes)")

# Ask user which file
choice = input("\nEnter file number to upload: ").strip()

try:
    file_idx = int(choice) - 1
    selected_file = files[file_idx]
except (ValueError, IndexError):
    print("❌ Invalid choice!")
    sys.exit(1)

print(f"\n✅ Selected: {selected_file.name}\n")

# Step 2: Upload to File Search Store
print("Step 2: Uploading to File Search Store...")
print("   What happens now:")
print("   1. File uploads to Google")
print("   2. Google chunks it (splits into pieces)")
print("   3. Google creates embeddings (vectors)")
print("   4. Google indexes it (searchable!)")
print()

# Start upload
operation = client.file_search_stores.upload_to_file_search_store(
    file=str(selected_file),
    file_search_store_name=store_name,
    config={'display_name': selected_file.stem}  # Filename without extension
)

print("⏳ Processing...", end="", flush=True)

# Wait for completion
while not operation.done:
    print(".", end="", flush=True)
    time.sleep(1)
    operation = client.operations.get(operation)

print(" DONE!\n")

# Step 3: Verify upload
print("Step 3: Verifying upload...")

docs = list(client.file_search_stores.documents.list(parent=store_name))

print(f"✅ Documents in store: {len(docs)}")
print("\nAll documents:")
for doc in docs:
    print(f"   📄 {doc.display_name}")

# Step 4: Show cost estimate
print_cost_estimate(selected_file.stat().st_size)

print("\n---")
print("What did we learn?")
print("- We uploaded a REAL file from /docs folder")
print("- Upload is async (takes a few seconds)")
print("- Embeddings are created automatically")
print("- File is now searchable!")
print("\n🎉 File successfully uploaded and indexed!")