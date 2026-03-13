"""
RAGAS Judge Model Compatibility Tester
---------------------------------------
Step 1: Raw LLM check — calls each model directly and prints the actual
        finish_reason coming back from langchain-google-genai. This tells
        us if the RAGAS LLMDidNotFinishException is a model issue or a
        finish_reason parsing mismatch between RAGAS and LangChain.

Step 2: RAGAS check — runs a single evaluate() call and checks for real
        numeric scores (NaN = FAIL, numeric = PASS).

Usage:
    python eval/test_judge.py
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from datasets import Dataset
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas import evaluate
from ragas.metrics import answer_relevancy, faithfulness

CANDIDATE_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]

DUMMY_DATASET = Dataset.from_list([
    {
        "question": "What is the capital of France?",
        "answer": "The capital of France is Paris.",
        "contexts": ["Paris is the capital and most populous city of France."],
        "ground_truth": "Paris",
    }
])


def check_raw_llm(model_name: str, api_key: str) -> tuple[bool, str]:
    """Call the model directly (no RAGAS) and return the finish_reason."""
    try:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=api_key,
            max_tokens=256,
        )
        msg = llm.invoke("Say hello in one word.")
        finish_reason = msg.response_metadata.get("finish_reason", "NOT_PRESENT")
        return True, f"finish_reason={finish_reason!r}"
    except Exception as exc:
        msg = str(exc)[:100]
        if "NOT_FOUND" in msg or "404" in msg:
            return False, "404 — model not available"
        return False, f"{type(exc).__name__}: {msg}"


def check_ragas(model_name: str, api_key: str) -> tuple[str, str]:
    """Run RAGAS evaluate() on 1 row. PASS = real numeric scores."""
    try:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=api_key,
            max_tokens=8192,
        )
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=api_key,
        )
        result = evaluate(
            dataset=DUMMY_DATASET,
            metrics=[faithfulness, answer_relevancy],
            llm=llm,
            embeddings=embeddings,
        )
        df = result.to_pandas()
        f = df["faithfulness"].iloc[0]
        r = df["answer_relevancy"].iloc[0]
        if math.isnan(f) and math.isnan(r):
            return "FAIL", "scores=NaN — LLMDidNotFinishException swallowed by RAGAS"
        return "PASS", f"faithfulness={round(float(f),3)} answer_relevancy={round(float(r),3)}"
    except Exception as exc:
        return "ERROR", f"{type(exc).__name__}: {str(exc)[:80]}"


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set.")
        sys.exit(1)

    print(f"\n{'='*70}")
    print("STEP 1 — RAW LLM CHECK (finish_reason diagnostic)")
    print(f"{'='*70}")
    available = []
    for model in CANDIDATE_MODELS:
        ok, notes = check_raw_llm(model, api_key)
        status = "OK" if ok else "SKIP"
        print(f"  {model:<30} {status:<6} {notes}")
        if ok:
            available.append(model)

    print(f"\n{'='*70}")
    print("STEP 2 — RAGAS EVALUATE CHECK (numeric scores required for PASS)")
    print(f"{'='*70}")
    print(f"  {'Model':<30} {'Result':<6} Notes")
    print(f"  {'-'*30} {'-'*6} {'-'*30}")
    passing = []
    for model in available:
        print(f"  Testing {model}...", flush=True)
        status, notes = check_ragas(model, api_key)
        print(f"\r  {model:<30} {status:<6} {notes}")
        if status == "PASS":
            passing.append(model)

    print(f"\n{'='*70}")
    if passing:
        print(f"Recommended judge: {passing[0]}")
    else:
        print("No models passed RAGAS check.")
        print("Likely cause: RAGAS v0.2.6 finish_reason mismatch with langchain-google-genai 2.x")
        print("Fix options:")
        print("  1. pip install 'langchain-google-genai==1.0.10'")
        print("  2. pip install 'ragas>=0.2.10'  (check for Gemini 2.x fix)")


if __name__ == "__main__":
    main()
