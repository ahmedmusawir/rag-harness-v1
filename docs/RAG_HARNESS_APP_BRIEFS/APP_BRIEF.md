# 🏭 APP_BRIEF: Managed RAG API + Streamlit Dev Rig

> **Status:** 🔒 LOCKED
> **Version:** 1.0
> **Project:** managed-rag-api-v1
> **Date:** 2026-03-07
> **Architect:** Tony Stark (Stark Industries AI Factory)

---

## 1. Mission Statement

Build a **FastAPI-based Managed RAG service** that wraps Google's File Search API into clean,
typed REST endpoints — plus a **Streamlit dev rig** that consumes those endpoints exactly as a
production Next.js frontend would. This becomes the Layer 3 RAG provider for the entire
Stark Industries AI Factory Agent Harness.

---

## 2. Hero Action

The developer creates a named agent/project, uploads documents via drag-and-drop, and queries
the resulting RAG store — all through a Streamlit UI that calls a local FastAPI backend.
The API is the product. Streamlit is the test harness.

---

## 3. Context & Lineage

This project is a direct evolution of `managed-rag-google-file-search-api-v1` (the discovery
tutorial). That repo's lesson scripts live in `reference/` as known-good SDK examples.
Codex must consult `reference/` before writing any File Search API calls — never use web docs
as the primary source of truth for this SDK.

---

## 4. User & Auth Scope

| Item | Value |
|------|-------|
| Persona | AI Engineer / Developer (Tony Stark only — single user) |
| Auth | None required (local dev rig) |
| Environment | macOS / WSL / Linux with Python 3.11+ |
| API Auth | Google Studio API Key via `.env` (`GEMINI_API_KEY`) |
| State | `projects.json` at repo root (plain JSON, no database) |

---

## 5. Tech Stack

| Layer | Technology |
|-------|-----------|
| API Backend | FastAPI + Uvicorn |
| RAG Provider | Google File Search API (`google-genai==1.55.0`) |
| Summary Generation | Gemini 2.5 Flash |
| Query Model | Gemini 2.5 Flash |
| State | `projects.json` (flat JSON file) |
| Frontend | Streamlit (dev rig only) |
| Config | `python-dotenv` + `.env` |
| Testing | `pytest` (clean venv compatible) |

---

## 6. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT DEV RIG                        │
│  (Mimics Next.js — all calls go through HTTP, no shortcuts) │
└─────────────────────────────┬───────────────────────────────┘
                              │ HTTP calls only
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                        │
│                                                             │
│  /projects          /projects/{id}/docs                     │
│  /projects/{id}/upload    /projects/{id}/query              │
│  /projects/{id}/docs/{doc_id} (DELETE)                      │
└─────────────────────────────┬───────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────┐         ┌─────────────────────────┐
│   projects.json     │         │  Google File Search API  │
│   (state store)     │         │  (RAG Provider)          │
└─────────────────────┘         └─────────────────────────┘
```

**Critical Rule:** Streamlit must NEVER import FastAPI service modules directly.
Every action must go through an HTTP call. This is non-negotiable.

---

## 7. The Ingestion Pipeline (Auto-Summary Pattern)

Every document upload follows this two-phase pipeline automatically:

```
User drops file
      │
      ▼
FastAPI receives file bytes
      │
      ▼
Phase 1: Gemini reads full doc → generates structured summary
      │        (model: gemini-2.5-flash)
      ▼
Phase 2: Upload ORIGINAL to File Search store
      │
      ▼
Phase 3: Upload SUMMARY to File Search store
      │
      ▼
Poll until both operations complete (async)
      │
      ▼
Write doc record to projects.json
      │
      ▼
Return success + doc metadata to Streamlit
```

**Why dual upload:** Chunking breaks counting/enumeration questions. The summary doc
compensates by giving the retriever a complete high-density representation. This pattern
is proven from the GHL API docs accuracy experiment.

---

## 8. API Endpoints (Full Scope)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/projects` | Create new agent/project + provision RAG store |
| `GET` | `/projects` | List all projects |
| `GET` | `/projects/{id}` | Get single project details |
| `DELETE` | `/projects/{id}` | Delete project + its RAG store |
| `POST` | `/projects/{id}/upload` | Upload doc (triggers auto-summary pipeline) |
| `GET` | `/projects/{id}/docs` | List all docs in project |
| `DELETE` | `/projects/{id}/docs/{doc_id}` | Delete single doc (force=True always) |
| `POST` | `/projects/{id}/query` | Query the RAG store, return answer + sources |

---

## 9. Streamlit UI — 3 Pages

### Left Pane (Persistent)
- New Project button (opens modal/form)
- Scrollable list of project names as clickable items
- Active project highlighted
- Project doc count shown as badge

### Page 1: Corpus Manager (Dashboard)
- Header: active project name + store ID
- Table: doc name | upload date | file size | status badge (Indexed / Processing / Failed)
- Checkbox per row for bulk selection
- Delete Selected button (top right)
- Refresh button

### Page 2: Upload
- Drag-and-drop file zone (PDF and TXT only — validate before upload)
- Accepted: `.pdf`, `.txt`
- Rejected: show inline error for all other types
- Progress indicator with multi-step status:
  - "Uploading..." → "Generating summary..." → "Indexing..." → "Done ✓"
- Completed doc appears in Corpus Manager automatically

### Page 3: Q&A Test
- Multi-turn chat (conversation history in Streamlit session state — not persisted)
- Active project shown in header
- Each answer displays grounding sources below it (doc name + chunk excerpt)
- Clear Conversation button
- Query goes to `POST /projects/{id}/query`

---

## 10. Scope Locks (Guardrails)

| ✅ IN SCOPE | 🚫 OUT OF SCOPE |
|-------------|-----------------|
| FastAPI backend with typed endpoints | Vertex RAG Engine |
| File Search API (google-genai SDK) | Supabase / any database |
| Auto-summary pipeline on every upload | Auth / RBAC |
| Streamlit dev rig (HTTP calls only) | Next.js frontend |
| `projects.json` for state | GCS / cloud storage |
| PDF + TXT file support | DOCX / image file support |
| Multi-turn Q&A in session state | Persistent conversation history |
| Grounding source display | Streaming responses |
| Delete doc + delete project | Batch re-indexing |
| `pytest` unit tests for service layer | Deployment pipelines |

---

## 11. File Structure

See `FILE_TREE.md` for the exact layout Codex must follow.

---

## 12. State Design

See `DATA_CONTRACT.md` for `projects.json` schema, all API request/response shapes,
and the summary pipeline contract.

---

## 13. Reference Material

Codex must read these files before writing any File Search API code:

| File | Purpose |
|------|---------|
| `reference/patterns.md` | Known-good SDK patterns (source of truth) |
| `reference/decisions.md` | Architectural decisions + gotchas |
| `reference/google_file_search_api.md` | Full API surface reference |
| `reference/lesson_3_upload_file.py` | Working async upload + polling pattern |
| `reference/lesson_4_query.py` | Working query pattern |
| `reference/lesson_5_create_summary.py` | Working summary generation pattern |

---

## 14. Success Definition

1. **Zero Guessing:** All 8 endpoints work without Codex asking for credentials or IDs.
2. **Pipeline Integrity:** Every upload automatically generates and uploads a summary doc.
3. **State Integrity:** `projects.json` is the single source of truth — no in-memory magic.
4. **API-First:** Streamlit never imports backend modules — HTTP only.
5. **Clean Venv:** `pytest` passes in a fresh virtual environment with no PYTHONPATH hacks.
6. **Accuracy:** Q&A test page shows grounding sources, proving RAG is working.

---

## 15. Build Sequence for Codex

Follow this order strictly — do not skip phases:

```
1. Project scaffold + requirements.txt + .env.example
2. projects.json state manager (read/write/validate)
3. Google File Search service layer (src/services/rag_service.py)
4. FastAPI app + all 8 endpoints (src/api/)
5. pytest tests for service layer
6. Streamlit app shell + left pane
7. Corpus Manager page
8. Upload page + pipeline progress
9. Q&A Test page + grounding display
10. Integration test: full upload → query flow
```

---

*Part of the Stark Industries AI Factory — managed-rag-api-v1*
*Version 1.0 | 2026-03-07*
