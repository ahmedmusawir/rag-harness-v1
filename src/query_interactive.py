#!/usr/bin/env python3
"""
Interactive Query Mode
Ask questions about your documents in real-time
"""
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

with open("store_name.txt", "r") as f:
    store_name = f.read().strip()

print("="*70)
print("  💬 INTERACTIVE QUERY MODE")
print("="*70)
print(f"\n📁 Store: {store_name}")

docs = list(client.file_search_stores.documents.list(parent=store_name))
print(f"📄 Documents: {', '.join([d.display_name for d in docs])}")

print("\n" + "="*70)
print("Ask questions about your documents (type 'exit' to quit)")
print("="*70 + "\n")

while True:
    question = input("❓ Your question: ").strip()
    
    if question.lower() in ['exit', 'quit', 'q']:
        print("\n👋 Goodbye!")
        break
    
    if not question:
        continue
    
    print("\n🤔 Thinking...\n")
    
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        # model="gemini-2.5-flash",
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
    
    print(f"✅ Answer:\n{response.text}\n")
    print("─"*70 + "\n")