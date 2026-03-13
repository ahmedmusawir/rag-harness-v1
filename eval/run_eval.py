"""
RAGAS v0.2 Baseline Eval Runner
--------------------------------
Reads eval/golden_dataset.json, runs all questions against the live
POST /projects/{id}/query endpoint, scores with RAGAS, writes receipts.

Usage:
    .venv/bin/python eval/run_eval.py

Env vars (optional):
    API_BASE_URL   default: http://localhost:8000
    API_KEY        default: "" (no auth)
    GEMINI_API_KEY required by langchain-google-genai judge
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import traceback
from datetime import datetime, timezone

import requests
from datasets import Dataset
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas import evaluate
from ragas.metrics import answer_relevancy, context_recall, faithfulness

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "").strip()
DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RECEIPTS_DIR = Path(__file__).parent / "receipts"
JUDGE_MODEL = "gemini-2.5-flash-lite"

HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}


def _score(val) -> float:
    """Convert a RAGAS metric value to float. Returns -1.0 for NaN/None (unscored)."""
    if val is None or str(val) == "nan":
        return -1.0
    return round(float(val), 4)


def _fmt(v: float) -> str:
    """Format a score for markdown output. Shows N/A for unscored (-1.0) rows."""
    return "N/A" if v == -1.0 else str(v)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _query(project_id: str, question: str) -> dict:
    url = f"{API_BASE_URL}/projects/{project_id}/query"
    resp = requests.post(url, json={"question": question}, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _contexts(sources: list[dict]) -> list[str]:
    return [s["chunk_text"] for s in sources if s.get("chunk_text")]


def _preflight(item: dict) -> None:
    print(f"\n{'='*60}")
    print("PRE-FLIGHT CHECK — Q001")
    print(f"{'='*60}")
    print(f"Question : {item['question']}")

    resp = _query(item["project_id"], item["question"])

    missing = [f for f in ("answer", "sources") if f not in resp]
    if missing:
        print(f"FAIL — missing fields in response: {missing}")
        sys.exit(1)

    sources = resp.get("sources", [])
    chunk_texts = [s.get("chunk_text") for s in sources]

    print(f"Answer   : {resp['answer'][:120]}...")
    print(f"Sources  : {len(sources)} returned")
    print(f"Chunks   : {[t[:60] + '...' if t and len(t) > 60 else t for t in chunk_texts]}")
    print(f"Latency  : {resp.get('latency_ms')}ms")

    if not any(chunk_texts):
        print("WARNING  : No chunk_text in any source — context_recall will be impaired")
    else:
        print("Shape    : OK — answer + sources[].chunk_text present")

    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # Load dataset
    if not DATASET_PATH.exists():
        print(f"ERROR: dataset not found at {DATASET_PATH}")
        sys.exit(1)

    with open(DATASET_PATH) as f:
        golden = json.load(f)

    print(f"Loaded {len(golden)} questions from {DATASET_PATH.name}")

    # Pre-flight
    _preflight(golden[0])
    proceed = input(f"Pre-flight passed. Run full eval on all {len(golden)} questions? [y/N]: ").strip().lower()
    if proceed != "y":
        print("Aborted.")
        sys.exit(0)

    # Build LLM judge — langchain-google-genai checks GOOGLE_API_KEY first,
    # so pass GEMINI_API_KEY explicitly since that's what this project uses.
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_api_key:
        print("ERROR: GEMINI_API_KEY or GOOGLE_API_KEY must be set in environment.")
        sys.exit(1)
    llm = ChatGoogleGenerativeAI(model=JUDGE_MODEL, temperature=0, google_api_key=gemini_api_key, max_tokens=8192)
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=gemini_api_key)

    # Run questions
    rows: list[dict] = []
    errors: list[dict] = []
    no_context_ids: list[str] = []

    for item in golden:
        qid = item["id"]
        question = item["question"]
        project_id = item["project_id"]
        ground_truth = item["ground_truth"]

        print(f"  [{qid}] {question[:70]}...")
        try:
            api_resp = _query(project_id, question)
            answer = api_resp["answer"]
            contexts = _contexts(api_resp.get("sources", []))

            if not contexts:
                print(f"    WARNING: no chunk_text returned — using placeholder")
                no_context_ids.append(qid)
                contexts = ["NO_CONTEXT_RETURNED"]

            rows.append({
                "question": question,
                "answer": answer,
                "contexts": contexts,
                "ground_truth": ground_truth,
                "_id": qid,
                "_no_context": qid in no_context_ids,
            })
        except Exception as exc:
            print(f"    ERROR: {exc}")
            errors.append({"id": qid, "question": question, "error": str(exc)})

    print(f"\nQuestions completed: {len(rows)} / {len(golden)}  |  Errors: {len(errors)}")
    if not rows:
        print("No rows to evaluate. Exiting.")
        sys.exit(1)

    # Build HuggingFace Dataset (RAGAS v0.2 expects this)
    hf_dataset = Dataset.from_list([
        {
            "question": r["question"],
            "answer": r["answer"],
            "contexts": r["contexts"],
            "ground_truth": r["ground_truth"],
        }
        for r in rows
    ])

    # Run RAGAS
    print("\nRunning RAGAS evaluation...")
    result = evaluate(
        dataset=hf_dataset,
        metrics=[faithfulness, answer_relevancy, context_recall],
        llm=llm,
        embeddings=embeddings,
    )

    scores_df = result.to_pandas()

    # Map scores back to question IDs
    per_question = []
    for i, row in enumerate(rows):
        qrow = scores_df.iloc[i] if i < len(scores_df) else {}
        per_question.append({
            "id": row["_id"],
            "question": row["question"],
            "faithfulness": _score(qrow.get("faithfulness")),
            "answer_relevancy": _score(qrow.get("answer_relevancy")),
            "context_recall": _score(qrow.get("context_recall")),
            "no_context_warning": row["_no_context"],
        })

    avg_faithfulness = _score(scores_df["faithfulness"].mean())
    avg_relevancy = _score(scores_df["answer_relevancy"].mean())
    avg_recall = _score(scores_df["context_recall"].mean())

    # Build receipt
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_slug = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    project_id = golden[0]["project_id"]

    receipt = {
        "timestamp": timestamp,
        "project_id": project_id,
        "dataset": DATASET_PATH.name,
        "total_questions": len(golden),
        "completed": len(rows),
        "errors": len(errors),
        "judge_model": JUDGE_MODEL,
        "summary": {
            "avg_faithfulness": avg_faithfulness,
            "avg_answer_relevancy": avg_relevancy,
            "avg_context_recall": avg_recall,
        },
        "no_context_warnings": no_context_ids,
        "per_question": per_question,
        "failures": errors,
    }

    # Write receipts
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECEIPTS_DIR / f"eval_{date_slug}.json"
    md_path = RECEIPTS_DIR / f"eval_{date_slug}.md"

    with open(json_path, "w") as f:
        json.dump(receipt, f, indent=2)

    # Markdown receipt
    no_ctx_flag = f"{len(no_context_ids)} questions had no context returned" if no_context_ids else "none"
    md_lines = [
        f"# RAGAS Eval Receipt — {date_slug}",
        "",
        f"**Timestamp:** {timestamp}  ",
        f"**Project ID:** {project_id}  ",
        f"**Dataset:** {DATASET_PATH.name}  ",
        f"**Questions:** {len(rows)} / {len(golden)} completed  ",
        f"**Judge model:** {JUDGE_MODEL}  ",
        f"**No-context warnings:** {no_ctx_flag}  ",
        "",
        "## Summary Scores",
        "",
        f"| Metric | Score |",
        f"|---|---|",
        f"| Context Recall | {avg_recall} |",
        f"| Faithfulness | {avg_faithfulness} |",
        f"| Answer Relevancy | {avg_relevancy} |",
        "",
        "## Per-Question Scores",
        "",
        "| ID | Question | Recall | Faithful | Relevancy | ⚠ |",
        "|---|---|---|---|---|---|",
    ]
    for pq in per_question:
        warn = "⚠" if pq["no_context_warning"] else ""
        q_short = pq["question"][:60] + "..." if len(pq["question"]) > 60 else pq["question"]
        md_lines.append(
            f"| {pq['id']} | {q_short} | {_fmt(pq['context_recall'])} | {_fmt(pq['faithfulness'])} | {_fmt(pq['answer_relevancy'])} | {warn} |"
        )

    if errors:
        md_lines += ["", "## Failures", ""]
        for e in errors:
            md_lines.append(f"- **{e['id']}** — {e['error']}")

    with open(md_path, "w") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"\n{'='*60}")
    print("EVAL COMPLETE")
    print(f"{'='*60}")
    print(f"Context Recall    : {avg_recall}")
    print(f"Faithfulness      : {avg_faithfulness}")
    print(f"Answer Relevancy  : {avg_relevancy}")
    print(f"No-context warns  : {len(no_context_ids)}")
    print(f"Errors            : {len(errors)}")
    print(f"\nReceipts written to:")
    print(f"  {json_path}")
    print(f"  {md_path}")


if __name__ == "__main__":
    main()
