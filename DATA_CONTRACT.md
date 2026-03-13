# Data Contract: managed-rag-api-v1

> **Status:** 🔒 LOCKED
> **Version:** 1.2
> **Date:** 2026-03-07

This document defines every data shape in the system. Codex must not deviate from
these contracts without explicit approval. If a shape needs to change, update this
file first.

---

## 1. State File: `projects.json`

**Location:** Repo root — `projects.json`
**Producer:** `src/services/state_service.py`
**Consumers:** All FastAPI route handlers

### Schema

```json
{
  "projects": {
    "{project_id}": {
      "id": "string (uuid4)",
      "name": "string",
      "description": "string (optional, default: '')",
      "store_id": "string (full resource path: fileSearchStores/name-hash)",
      "created_at": "string (ISO 8601: 2026-03-07T14:31:00Z)",
      "doc_count": "integer (DERIVED — always equals len(docs))",
      "docs": {
        "{doc_id}": {
          "id": "string (uuid4)",
          "project_id": "string (uuid4)",
          "original_name": "string (filename.pdf)",
          "display_name": "string (filename without extension)",
          "file_size_bytes": "integer",
          "mime_type": "string (application/pdf | text/plain)",
          "store_doc_name": "string (full resource path from File Search API)",
          "summary_doc_name": "string (full resource path of summary doc)",
          "status": "string (enum — see Status Enum below)",
          "uploaded_at": "string (ISO 8601)",
          "error": "string (optional, null if no error)"
        }
      }
    }
  }
}
```

### doc_count Rule (Critical)

`doc_count` is a **derived field**. It must never be manually set or incremented.

```python
# The ONLY correct way to update doc_count:
project["doc_count"] = len(project["docs"])
```

`state_service.py` must recalculate `doc_count` after every add or remove operation.
Any code that manually increments or decrements `doc_count` is a bug.

### Status Enum (Frozen)

`status` must be exactly one of these three values. No other values are permitted:

| Value | Meaning |
|-------|---------|
| `"processing"` | Upload in progress — not yet queryable |
| `"indexed"` | Successfully chunked, embedded, and indexed — ready to query |
| `"failed"` | Upload or indexing failed — see `error` field for detail |

Codex must not invent new status values (e.g. `"complete"`, `"ready"`, `"done"`).

### Example

```json
{
  "projects": {
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890": {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Architect Agent",
      "description": "Docs for the Stark Architect Jarvis agent",
      "store_id": "fileSearchStores/architect-agent-wsb9ns3bu5m0",
      "created_at": "2026-03-07T14:31:00Z",
      "doc_count": 1,
      "docs": {
        "f1e2d3c4-b5a6-7890-fedc-ba0987654321": {
          "id": "f1e2d3c4-b5a6-7890-fedc-ba0987654321",
          "project_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "original_name": "APP_ARCHITECTURE_MANUAL.pdf",
          "display_name": "APP_ARCHITECTURE_MANUAL",
          "file_size_bytes": 245760,
          "mime_type": "application/pdf",
          "store_doc_name": "fileSearchStores/architect-agent-wsb9ns3bu5m0/documents/app-architecture-manual-abc123",
          "summary_doc_name": "fileSearchStores/architect-agent-wsb9ns3bu5m0/documents/app-architecture-manual-summary-def456",
          "status": "indexed",
          "uploaded_at": "2026-03-07T14:35:00Z",
          "error": null
        }
      }
    }
  }
}
```

### Read Rule

```python
with open("projects.json", "r") as f:
    data = json.load(f)
```

Always use `.get()` for optional fields. Never assume a key exists.

### Write Rule

Always read → modify → write atomically. Never partially write.

### Validation Rule

If `projects.json` is missing, create it with `{"projects": {}}`.
If a project_id is not found, return HTTP 404.
If `store_id` is empty string, the project is in an error state — do not attempt queries.

---

## 2. API Request / Response Shapes

### GET /health

**Response 200:**
```json
{
  "status": "ok"
}
```

No auth required. Used for Cloud Run readiness probes.

---

### POST /projects — Create Project

**Request Body:**
```json
{
  "name": "string (required, 1-100 chars)",
  "description": "string (optional, default: '')"
}
```

**Response 201:**
```json
{
  "id": "string (uuid4)",
  "name": "string",
  "description": "string",
  "store_id": "string",
  "created_at": "string (ISO 8601)",
  "doc_count": 0
}
```

**Response 422:** Validation error (name missing or too long)
**Response 500:** Google API failure — include `detail` field with message

---

### GET /projects — List Projects

**Response 200:**
```json
{
  "projects": [
    {
      "id": "string",
      "name": "string",
      "description": "string",
      "store_id": "string",
      "created_at": "string",
      "doc_count": 0
    }
  ]
}
```

Returns empty array `[]` if no projects exist — never 404.

---

### GET /projects/{id} — Get Project

**Response 200:** Same shape as single project object above, plus full `docs` map.
**Response 404:** `{"detail": "Project not found"}`

---

### DELETE /projects/{id} — Delete Project

**Response 200:**
```json
{
  "message": "Project deleted successfully",
  "id": "string"
}
```

**Response 404:** `{"detail": "Project not found"}`

Implementation note: Delete all docs from the File Search store first (force=True),
then delete the store, then remove from projects.json.

---

### POST /projects/{id}/upload — Upload Document

**Request:** `multipart/form-data`
- `file`: binary file upload
- Accepted MIME types: `application/pdf`, `text/plain`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `application/vnd.openxmlformats-officedocument.presentationml.presentation`, `text/csv`, `text/markdown`, `text/html`, `application/json`, `application/rtf`
- Accepted extensions: `.pdf`, `.txt`, `.docx`, `.xlsx`, `.pptx`, `.csv`, `.md`, `.html`, `.json`, `.rtf`
- Both checks must pass — reject mismatches
- Max file size: 50MB

#### Timeout / Safety Valve (Critical)

This endpoint blocks while polling Google's async File Search operations.
Google's API can stall. The Streamlit UI must never hang indefinitely.

Rules:
- Total timeout budget: **90 seconds** across the full pipeline
- If any polling loop exceeds its share of the timeout budget, stop immediately
- Return **HTTP 504** with `{"detail": "Upload timed out. Google API did not respond within 90 seconds."}` 
- The FastAPI endpoint must implement this via `asyncio.wait_for` or equivalent
- The Streamlit UI must handle 504 and show: `"Upload timed out. Please try again."`
- Do NOT let the request hang — a clean timeout error is always better than a frozen UI

**Response 200 (success):**
```json
{
  "doc_id": "string (uuid4)",
  "original_name": "string",
  "display_name": "string",
  "file_size_bytes": "integer",
  "status": "indexed",
  "store_doc_name": "string",
  "summary_doc_name": "string",
  "uploaded_at": "string (ISO 8601)"
}
```

**Response 400:** `{"detail": "File type not supported. Accepted: PDF, TXT"}`
**Response 400:** `{"detail": "Project has reached the 200 document limit."}`
**Response 404:** `{"detail": "Project not found"}`
**Response 500:** `{"detail": "Upload failed: {error message}"}`
**Response 504:** `{"detail": "Upload timed out. Google API did not respond within 90 seconds."}`

---

### GET /projects/{id}/docs — List Documents

**Response 200:**
```json
{
  "docs": [
    {
      "id": "string",
      "original_name": "string",
      "display_name": "string",
      "file_size_bytes": "integer",
      "mime_type": "string",
      "status": "string (processing | indexed | failed)",
      "uploaded_at": "string",
      "error": "string | null"
    }
  ]
}
```

---

### DELETE /projects/{id}/docs/{doc_id} — Delete Document

**Response 200:**
```json
{
  "message": "Document deleted successfully",
  "doc_id": "string"
}
```

**Response 404:** `{"detail": "Document not found"}`

Implementation note: Delete BOTH `store_doc_name` AND `summary_doc_name` from
the File Search store (force=True on both). Then remove from projects.json.
Recalculate `doc_count = len(docs)` after removal.

---

### GET /projects/{id}/store/check

**Response 200:**
```json
{
  "project_id": "string",
  "project_name": "string",
  "store_id": "string",
  "document_count": 2,
  "documents": [
    {
      "name": "string",
      "display_name": "string"
    }
  ]
}
```

---

### GET /projects/{id}/store/details

**Response 200:**
```json
{
  "project_id": "string",
  "project_name": "string",
  "store_id": "string",
  "store_display_name": "string",
  "doc_count": 2,
  "raw": {}
}
```

---

### GET /projects/{id}/store/documents

**Response 200:**
```json
{
  "project_id": "string",
  "store_id": "string",
  "document_count": 2,
  "documents": [
    {
      "name": "string",
      "display_name": "string"
    }
  ]
}
```

---

### GET /projects/{id}/store/documents/{document_name} — Get Document Details

**Response 200:**
```json
{
  "name": "string",
  "display_name": "string",
  "raw": {}
}
```

---

### GET /stores/verify

**Response 200:**
```json
{
  "total_stores": 1,
  "stores": [
    {
      "name": "string",
      "display_name": "string",
      "document_count": 2
    }
  ]
}
```

---

### POST /projects/{id}/store/cleanup-preview

**Response 200:**
```json
{
  "project_id": "string",
  "project_name": "string",
  "store_id": "string",
  "doc_count": 2,
  "docs": [],
  "warning": "string"
}
```

---

### POST /projects/{id}/store/cleanup

**Request Body:**
```json
{
  "confirm": true,
  "confirmation_text": "EMPTY STORE"
}
```

**Locked Behavior (Non-Negotiable):**
- Delete all documents from the Google store (`force=True`)
- Clear all docs from that project in `projects.json`
- Recalculate `doc_count = 0`
- Keep the project record intact
- Keep the store intact
- Never delete the project
- Never delete the store

**Response 200:**
```json
{
  "project_id": "string",
  "store_id": "string",
  "deleted_count": 2,
  "doc_count": 0,
  "message": "string"
}
```

**Response 400:** `{"detail": "Cleanup requires confirm=true and confirmation_text='EMPTY STORE'."}`

---

### GET /operations/{operation_name}

**Response 200:**
```json
{
  "name": "string",
  "done": true,
  "metadata": {},
  "error": null
}
```

---

### POST /projects/{id}/query — Query RAG Store

**Request Body:**
```json
{
  "question": "string (required, 1-2000 chars)",
  "model": "string (optional, default: 'gemini-2.5-pro')"
}
```

**Response 200:**
```json
{
  "answer": "string",
  "sources": [
    {
      "doc_name": "string",
      "chunk_text": "string (excerpt from grounding metadata)",
      "relevance_score": "float | null"
    }
  ],
  "model_used": "string",
  "project_id": "string",
  "latency_ms": "integer (server-side measurement — useful for RAG debugging)"
}
```

`latency_ms` is measured server-side from the moment `generate_content` is called
to the moment the response is received. Use `time.perf_counter()` for precision.

**Response 400:** `{"detail": "Question cannot be empty"}`
**Response 404:** `{"detail": "Project not found"}`
**Response 500:** `{"detail": "Query failed: {error message}"}`

---

## 3. Summary Pipeline Contract

The auto-summary is generated by Gemini before upload. This is handled entirely
inside `src/services/rag_service.py` — not exposed as a separate endpoint.

### Summary Prompt (Canonical — do not modify without approval)

```python
SUMMARY_PROMPT = """
Analyze this document and create a STRUCTURED SUMMARY for search and retrieval:

1. DOCUMENT TYPE: (What kind of document is this?)

2. MAIN TOPICS: (3-5 key topics covered)

3. KEY ENTITIES — LIST ALL:
   - People mentioned (full names)
   - Companies / Organizations (ALL of them, including brief mentions)
   - Important dates
   - Important numbers / metrics

4. MAIN POINTS: (Key takeaways in bullet points)

5. SEARCHABLE KEYWORDS: (Important terms someone might search for)

Be EXHAUSTIVE with entities — list EVERY company, person, date mentioned.
This summary will be used for search and retrieval. Completeness matters.
"""
```

### Summary Doc Naming Convention

```
Original display name:  APP_ARCHITECTURE_MANUAL
Summary display name:   APP_ARCHITECTURE_MANUAL_SUMMARY
```

---

## 4. Environment Variables (.env)

```bash
# Required
GEMINI_API_KEY=your_google_studio_api_key_here

# Optional overrides
API_HOST=127.0.0.1
API_PORT=8000
MAX_FILE_SIZE_MB=50
UPLOAD_TIMEOUT_SECONDS=90
SUMMARY_REQUIRED=true
```

`.env.example` must be committed. `.env` must be in `.gitignore`.
All env vars must be loaded exclusively via `src/services/config_service.py`.
No other module may call `os.getenv()` directly.

---

## 5. Pydantic Types Location

All Pydantic models live in `src/types/`.
Import path: `from src.types.project import ProjectCreate, ProjectResponse`
Import path: `from src.types.doc import DocResponse, QueryRequest, QueryResponse`

Note: This is `src/types/` — NOT `src/models/`. Tony's standard is `/types` for all
data shapes and interfaces.

---

## 6. Error Response Shape (All Endpoints)

All errors use FastAPI's standard HTTPException shape:

```json
{
  "detail": "Human-readable error message"
}
```

No nested error objects. No stack traces in responses.
Log full exceptions server-side only via `logging_service.py`.

---

*Part of the Stark Industries AI Factory — managed-rag-api-v1*
*Version 1.2 | 2026-03-07*
