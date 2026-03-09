#!/usr/bin/env python3
"""
LESSON 4: Query Your Documents
Test RAG retrieval quality - see how accurate answers are
"""
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

load_dotenv()

print("="*70)
print("  🔍 LESSON 4: QUERY YOUR DOCUMENTS")
print("="*70)

# Create client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Load store
with open("store_name.txt", "r") as f:
    store_name = f.read().strip()

print(f"\n📁 Using store: {store_name}")

# Check what's in the store
docs = list(client.file_search_stores.documents.list(parent=store_name))
print(f"📄 Documents: {len(docs)}")
for doc in docs:
    print(f"   - {doc.display_name}")

print("\n" + "="*70)
print("  💬 RAG QUALITY TEST")
print("="*70)

# Test questions about your resume
test_questions = [
    "What is Moose's primary technical expertise?",
    "What current projects is Moose working on?",
    "What AI/ML technologies does Moose work with?",
    "What is Moose's experience with Google Cloud Platform?",
]

print("\n🧪 Testing RAG retrieval quality...")
print("   (Ask specific questions about the resume)\n")

for i, question in enumerate(test_questions, 1):
    print(f"\n{'─'*70}")
    print(f"Question {i}: {question}")
    print('─'*70)
    
    # Query with File Search
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=question,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store_name]
                    )
                )
            ]
        )
    )
    
    print(f"\n✅ Answer:\n{response.text}")
    
    # Show grounding metadata (citations)
    if hasattr(response.candidates[0], 'grounding_metadata'):
        metadata = response.candidates[0].grounding_metadata
        print(f"\n📚 Grounding Info:")
        print(f"   {metadata}")

print("\n" + "="*70)
print("  🎯 RAG QUALITY ASSESSMENT")
print("="*70)

print("""
Now YOU evaluate the quality:

✅ Did it answer accurately from your resume?
✅ Did it hallucinate any information?
✅ Did it cite the source document?
✅ How does this compare to your Langchain RAG?

💡 Tips for better RAG:
- More specific questions = better retrieval
- Shorter documents = better accuracy
- Related docs in same store = better context
""")