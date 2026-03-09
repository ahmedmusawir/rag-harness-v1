#!/usr/bin/env python3
"""
LESSON 5: Create Structured Summary
Use LLM to extract key facts into a structured summary
This helps RAG answer counting/listing questions accurately
"""
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()

print("="*70)
print("  📋 LESSON 5: CREATE STRUCTURED SUMMARY")
print("="*70)

# Create client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Step 1: Read the PDF
print("\nStep 1: Reading moose_resume.pdf...")

pdf_path = Path("docs/moose_resume.pdf")

if not pdf_path.exists():
    print("❌ moose_resume.pdf not found in /docs!")
    exit(1)

# Read PDF as bytes
with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()

print(f"✅ Loaded PDF ({len(pdf_bytes):,} bytes)")

# Step 2: Ask LLM to create structured summary
print("\nStep 2: Generating structured summary with Gemini...")
print("   (This will take a few seconds...)\n")

summary_prompt = """
Analyze this resume and create a STRUCTURED SUMMARY with the following sections:

1. FULL NAME AND CONTACT
2. TOTAL COMPANIES WORKED FOR (count them ALL, including freelance)
3. COMPLETE COMPANY LIST (list EVERY company with dates):
   - Company Name (Start Date - End Date)
   
4. EDUCATION:
   - Degree, University, Years
   
5. TOP SKILLS (list main technologies)

6. CURRENT ROLE AND FOCUS

Be EXHAUSTIVE - include EVERY company mentioned, even brief ones.
List companies in reverse chronological order (most recent first).

Format the summary clearly with headers and bullet points.
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Part.from_bytes(
            data=pdf_bytes,
            mime_type="application/pdf"
        ),
        summary_prompt  # ✅ Just pass as string!
    ]
)

summary_text = response.text

print("✅ Summary generated!\n")
print("="*70)
print("GENERATED SUMMARY:")
print("="*70)
print(summary_text)
print("="*70)

# Step 3: Save summary to file
print("\nStep 3: Saving summary...")

summary_path = Path("docs/moose_resume_SUMMARY.txt")
summary_path.write_text(summary_text)

print(f"✅ Saved to: {summary_path}")
print(f"   Size: {summary_path.stat().st_size:,} bytes")

print("\n" + "="*70)
print("What did we learn?")
print("- LLM can read full PDF and extract structured info")
print("- Summary contains ALL companies (not missed by chunking)")
print("- Summary is optimized for counting/listing questions")
print("\n📌 Next: Upload this summary to File Search Store!")
print("="*70)