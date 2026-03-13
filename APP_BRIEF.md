# 🏭 APP_BRIEF: Managed RAG API + Streamlit Dev Rig

> **Status:** 🔒 LOCKED
> **Version:** 1.2
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
| Auth | X-API-Key header middleware (optional locally, required when deployed) |
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
| Config | `python-dotenv` + `.env` via `config_service.py` |
| Logging | Centralized via `logging_service.py` |
| Testing | `pytest` (clean venv compatible) |
| API Security | X-API-Key header middleware |

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
│  GET  /health                                               │
│  POST /projects          GET  /projects                     │
│  GET  /projects/{id}     DELETE /projects/{id}              │
│  POST /projects/{id}/upload                                 │
│  GET  /projects/{id}/docs                                   │
│  DELETE /projects/{id}/docs/{doc_id}                        │
│  POST /projects/{id}/query                                  │
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

Every document upload follows this two-phase pipeline automatically.

**Fail-fast rule:** If summary generation fails, abort the entire upload.
Do NOT upload the original document. Return status `"failed"` with error detail.
The summary is a core part of the indexing strategy — not optional.

> ⚠️ Escape hatch: If Gemini summary generation proves flaky in practice, set
> `SUMMARY_REQUIRED=false` in `.env` to fall back to original-only upload.
> Log a warning when fallback is triggered. Default behavior is always fail-fast.

```
User drops file
      │
      ▼
Validate: MIME type AND file extension (.pdf / .docx / .xlsx / .pptx / .txt / .csv / .md / .html / .json / .rtf)
      │ fail → return 400 immediately
      ▼
Check doc count < 200 (soft limit per project)
      │ fail → return 400 immediately
      ▼
FastAPI receives file bytes
      │
      ▼
Phase 1: Gemini reads full doc → generates structured summary
         (model: gemini-2.5-flash)
      │ fail → abort entirely, return 500, do NOT proceed to upload
      ▼
Phase 2: Upload ORIGINAL to File Search store + poll until indexed
         (timeout: 90 seconds)
      │ timeout → return 504
      ▼
Phase 3: Upload SUMMARY to File Search store + poll until indexed
         (timeout: 90 seconds)
      │ timeout → return 504
      ▼
Write doc record to projects.json (status: "indexed")
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
| `GET` | `/health` | Returns `{"status": "ok"}` — used for Cloud Run readiness |
| `POST` | `/projects` | Create new agent/project + provision RAG store |
| `GET` | `/projects` | List all projects |
| `GET` | `/projects/{id}` | Get single project details |
| `DELETE` | `/projects/{id}` | Delete project + its RAG store |
| `POST` | `/projects/{id}/upload` | Upload doc (triggers auto-summary pipeline) |
| `GET` | `/projects/{id}/docs` | List all docs in project |
| `DELETE` | `/projects/{id}/docs/{doc_id}` | Delete single doc (force=True always) |
| `POST` | `/projects/{id}/query` | Query the RAG store, return answer + sources |

---

## 9. File Validation Rules

Every upload must pass **both** checks before processing begins:

| Check | Allowed Values |
|-------|---------------|
| MIME type | `application/pdf`, `text/plain`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `application/vnd.openxmlformats-officedocument.presentationml.presentation`, `text/csv`, `text/markdown`, `text/html`, `application/json`, `application/rtf` |
| File extension | `.pdf`, `.txt`, `.docx`, `.xlsx`, `.pptx`, `.csv`, `.md`, `.html`, `.json`, `.rtf` |

Reject if either check fails — return HTTP 400.
Reject MIME/extension mismatches (e.g. a `.txt` file with PDF MIME type).

---

## 10. Guardrails

| Guardrail | Rule |
|-----------|------|
| Max docs per project | 200 (soft limit) — return HTTP 400 if exceeded |
| Max file size | 50MB — return HTTP 400 if exceeded |
| Upload timeout | 90 seconds total — return HTTP 504 if Google API stalls |
| Summary failure | Abort upload — do not partially ingest |

---

## 11. Streamlit UI — 3 Pages

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
- Drag-and-drop file zone (all Google File Search supported formats)
- Accepted: `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.txt`, `.csv`, `.md`, `.html`, `.json`, `.rtf`
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

## 12. Scope Locks (Guardrails)

| ✅ IN SCOPE | 🚫 OUT OF SCOPE |
|-------------|-----------------|
| FastAPI backend with typed endpoints | Vertex RAG Engine |
| File Search API (google-genai SDK) | Supabase / any database |
| Auto-summary pipeline on every upload | Auth / RBAC |
| Streamlit dev rig (HTTP calls only) | Next.js frontend |
| `projects.json` for state | GCS / cloud storage |
| PDF, DOCX, XLSX, PPTX, TXT, CSV, MD, HTML, JSON, RTF support | Image file support |
| Multi-turn Q&A in session state | Persistent conversation history |
| Grounding source display | Streaming responses |
| Delete doc + delete project | Batch re-indexing |
| `pytest` unit tests for service layer | Deployment pipelines |
| X-API-Key middleware | OAuth / JWT auth |
| Health endpoint | Metrics / observability |
| Centralized config + logging | Third-party log services |

---

## 13. File Structure

See `FILE_TREE.md` for the exact layout Codex must follow.

---

## 14. State Design

See `DATA_CONTRACT.md` for `projects.json` schema, all API request/response shapes,
and the summary pipeline contract.

---

## 15. Reference Material

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

## 16. Build Sequence for Codex

Follow Tony's TDD flow strictly for every module:

```
Build → Unit Test → Integrate → Block Test → System Test → Finalize
```

**Do not move to the next step until the current step passes.**

```
STEP 1 — Project scaffold
         requirements.txt, .env.example, .gitignore
         main.py shell, folder structure
         ✅ Verify: clean install works in fresh venv

STEP 2 — Config + Logging services
         src/services/config_service.py
         src/services/logging_service.py
         ✅ Unit test: config loads all required vars from .env
         ✅ Unit test: missing GEMINI_API_KEY raises clear error
         ✅ Verify: pytest passes in clean venv

STEP 3 — State service
         src/services/state_service.py
         projects.json CRUD (create, read, update, delete)
         ✅ Unit test: test_state_service.py — all CRUD operations
         ✅ Unit test: missing projects.json auto-creates correctly
         ✅ Unit test: doc_count always equals len(docs)
         ✅ Verify: pytest passes in clean venv

STEP 4 — RAG service (Google File Search API)
         src/services/rag_service.py
         store create/delete, upload + poll, summary gen, query, doc delete
         ✅ Unit test: test_rag_service.py — all methods mocked
         ✅ Unit test: upload timeout returns correct error shape
         ✅ Unit test: summary failure aborts pipeline correctly
         ✅ Verify: pytest passes in clean venv

STEP 5 — Pydantic types
         src/types/project.py
         src/types/doc.py
         ✅ Unit test: all shapes validate against DATA_CONTRACT.md exactly
         ✅ Verify: pytest passes in clean venv

STEP 6 — FastAPI routers
         src/api/health.py
         src/api/projects.py
         src/api/docs.py
         ✅ Integration test: test_api.py — all 9 endpoints with httpx
         ✅ Block test: full create → upload → list → query → delete flow
         ✅ Verify: pytest passes in clean venv

STEP 7 — System test (live API)
         ✅ Run full flow end-to-end against live Google API
         ✅ Confirm grounding sources returned on query
         ✅ Confirm doc_count stays in sync after add/delete
         ✅ Confirm 504 returned on simulated timeout

STEP 8 — Streamlit shell + sidebar
         src/streamlit/app.py
         src/streamlit/components/sidebar.py
         src/streamlit/api_client.py
         ✅ Manual test: project list loads, new project dialog works
         ✅ Manual test: API unreachable shows correct error

STEP 9 — Corpus Manager page
         src/streamlit/pages/corpus_manager.py
         ✅ Manual test: doc list renders with correct status badges
         ✅ Manual test: delete with confirm removes doc from list

STEP 10 — Upload page
          src/streamlit/pages/upload.py
          src/streamlit/components/progress.py
          ✅ Manual test: drag-drop → spinner → success → doc in corpus
          ✅ Manual test: invalid file type shows inline error

STEP 11 — Q&A Test page
          src/streamlit/pages/qa_test.py
          ✅ Manual test: multi-turn chat works
          ✅ Manual test: sources display collapsed under each answer
          ✅ Manual test: clear chat resets history

STEP 12 — Finalize
          ✅ Full system test: create project → upload 2 docs → query → delete
          ✅ All pytest tests pass in clean venv
          ✅ README.md written with setup + run instructions
```

---

## 17. Success Definition

1. **Zero Guessing:** All 9 endpoints work without Codex asking for credentials or IDs.
2. **Pipeline Integrity:** Every upload automatically generates and uploads a summary doc.
3. **Fail Fast:** Failed summary aborts upload — no partial ingestion.
4. **State Integrity:** `projects.json` is the single source of truth — `doc_count` always equals `len(docs)`.
5. **API-First:** Streamlit never imports backend modules — HTTP only.
6. **Clean Venv:** `pytest` passes in a fresh virtual environment with no PYTHONPATH hacks.
7. **Accuracy:** Q&A test page shows grounding sources, proving RAG is working.
8. **TDD Enforced:** No module ships without passing its unit tests first.

---

*Part of the Stark Industries AI Factory — managed-rag-api-v1*
*Version 1.2 | 2026-03-07*
