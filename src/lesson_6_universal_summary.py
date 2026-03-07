#!/usr/bin/env python3
"""
LESSON 5B: Universal Summary Prompt
Test a generic prompt that works for ANY document type
"""
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()

print("="*70)
print("  📋 LESSON 5B: UNIVERSAL SUMMARY PROMPT")
print("="*70)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Read PDF
pdf_path = Path("docs/moose_resume.pdf")
with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()

print(f"\n✅ Loaded PDF ({len(pdf_bytes):,} bytes)")

# UNIVERSAL PROMPT (works for any document!)
universal_prompt = """
Analyze this document and create a STRUCTURED SUMMARY:

1. DOCUMENT TYPE: (What kind of document is this?)

2. MAIN TOPICS: (What are the 3-5 key topics covered?)

3. KEY ENTITIES - LIST ALL:
   - People mentioned (full names)
   - Companies/Organizations mentioned (ALL of them)
   - Important dates (when available)
   - Important numbers/metrics (when available)

4. MAIN POINTS: (Summarize the key takeaways in bullet points)

5. SEARCHABLE KEYWORDS: (List important terms someone might search for)

Be EXHAUSTIVE with entities - list EVERY company, person, date mentioned.
This summary will be used for search and retrieval, so completeness matters.
"""

print("\nGenerating UNIVERSAL summary...")
print("(This prompt works for resumes, docs, emails, anything!)\n")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        universal_prompt
    ]
)

summary_text = response.text

print("="*70)
print("UNIVERSAL SUMMARY:")
print("="*70)
print(summary_text)
print("="*70)

# Save it
summary_path = Path("docs/moose_resume_UNIVERSAL_SUMMARY.txt")
summary_path.write_text(summary_text)

print(f"\n✅ Saved to: {summary_path}")

print("\n" + "="*70)
print("DID IT WORK?")
print("="*70)
print("Check if it listed ALL companies (should be 9)")
print("This prompt works for ANY document type Coach uploads!")
print("="*70)