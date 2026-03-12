#!/usr/bin/env python3
"""
Cleanup Store - Interactive Document Management
Choose to delete specific docs or all docs
"""
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

print("="*70)
print("  🗑️  DOCUMENT CLEANUP")
print("="*70)

# Create client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Load store
with open("store_name.txt", "r") as f:
    store_name = f.read().strip()

print(f"\n📁 Store: {store_name}")

# Get all documents
docs = list(client.file_search_stores.documents.list(parent=store_name))

if len(docs) == 0:
    print("\n✅ Store is already empty!")
    print("   Nothing to delete.")
    exit(0)

print(f"\n📋 Documents in store: {len(docs)}")

# Show all documents with numbers
print("\nSelect document to delete:\n")
for i, doc in enumerate(docs, 1):
    print(f"   {i}. 📄 {doc.display_name}")

print(f"\n   {len(docs) + 1}. 🗑️  DELETE ALL")
print(f"   0. ❌ Cancel (don't delete anything)")

# Get user choice
choice = input(f"\nEnter your choice (0-{len(docs) + 1}): ").strip()

try:
    choice_num = int(choice)
except ValueError:
    print("❌ Invalid input!")
    exit(1)

# Handle choices
if choice_num == 0:
    print("\n✅ Cancelled. No documents deleted.")
    exit(0)

elif choice_num == len(docs) + 1:
    # Delete all
    print("\n⚠️  WARNING: This will delete ALL documents!")
    confirm = input("Confirm? (y/yes): ").strip().lower()
    
    if confirm not in ['y', 'yes']:
        print("\n✅ Cancelled.")
        exit(0)
    
    print("\n🗑️  Deleting all documents...")
    for doc in docs:
        print(f"   Deleting: {doc.display_name}")
        client.file_search_stores.documents.delete(
            name=doc.name,
            config={'force': True}  # ✅ FIXED: Force delete with chunks
        )
    
    print(f"\n✅ Deleted {len(docs)} document(s)!")

elif 1 <= choice_num <= len(docs):
    # Delete specific document
    doc_to_delete = docs[choice_num - 1]
    
    print(f"\n🗑️  Deleting: {doc_to_delete.display_name}")
    
    confirm = input("Confirm? (y/yes): ").strip().lower()
    
    if confirm in ['y', 'yes']:
        client.file_search_stores.documents.delete(
            name=doc_to_delete.name,
            config={'force': True}  # ✅ FIXED: Force delete with chunks
        )
        print("\n✅ Document deleted!")
    else:
        print("\n✅ Cancelled.")
else:
    print("❌ Invalid choice!")

print("\n" + "="*70)
print("Run 'python src/check_store.py' to verify")
print("="*70)