# Data Contract: managed-rag-api-v1

> **Status:** 🔒 LOCKED
> **Version:** 1.0
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
      "doc_count": "integer",
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
          "status": "string (processing | indexed | failed)",
          "uploaded_at": "string (ISO 8601)",
          "error": "string (optional, null if no error)"
        }
      }
    }
  }
}
```

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
      "doc_count": 3,
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
- Accepted MIME types: `application/pdf`, `text/plain`
- Max file size: 50MB

**Response 200 (streaming status updates via polling):**

The endpoint is synchronous but the pipeline is multi-step.
Return final result only after all steps complete.

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
**Response 404:** `{"detail": "Project not found"}`
**Response 500:** `{"detail": "Upload failed: {error message}"}`

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
      "status": "string",
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

---

### POST /projects/{id}/query — Query RAG Store

**Request Body:**
```json
{
  "question": "string (required, 1-2000 chars)",
  "model": "string (optional, default: 'gemini-2.5-flash')"
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
  "project_id": "string"
}
```

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
```

`.env.example` must be committed. `.env` must be in `.gitignore`.

---

## 5. Error Response Shape (All Endpoints)

All errors use FastAPI's standard HTTPException shape:

```json
{
  "detail": "Human-readable error message"
}
```

No nested error objects. No stack traces in responses.
Log full exceptions server-side only.

---

*Part of the Stark Industries AI Factory — managed-rag-api-v1*
*Version 1.0 | 2026-03-07*
