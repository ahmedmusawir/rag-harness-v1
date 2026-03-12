# File Tree: managed-rag-api-v1

> **Status:** 🔒 LOCKED
> **Version:** 1.2
> **Date:** 2026-03-07

This is the exact folder and file structure Codex must produce.
Do not create files not listed here. Do not rename files listed here.
If a new file is needed, propose it and wait for approval.

---

## Full Tree

```
managed-rag-api-v1/
│
├── reference/                          ← READ-ONLY reference from discovery repo
│   ├── patterns.md                     ← Known-good SDK patterns (PRIMARY reference)
│   ├── decisions.md                    ← Architectural decisions + gotchas
│   ├── google_file_search_api.md       ← Full API surface reference
│   ├── lesson_1_check_api.py
│   ├── lesson_2_create_store.py
│   ├── lesson_3_upload_file.py         ← Working async upload + polling
│   ├── lesson_4_query.py               ← Working query pattern
│   ├── lesson_5_create_summary.py      ← Working summary generation
│   └── lesson_6_universal_summary.py
│
├── src/
│   ├── services/
│   │   ├── __init__.py
│   │   ├── config_service.py           ← Centralized .env loading (ONLY place os.getenv is called)
│   │   ├── logging_service.py          ← Centralized logger — all services import from here
│   │   ├── rag_service.py              ← All File Search API calls live here
│   │   └── state_service.py            ← projects.json read/write/validate
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py             ← X-API-Key dependency (optional locally, enforced when configured)
│   │   ├── diagnostics.py              ← Dev diagnostics + cleanup endpoints
│   │   ├── health.py                   ← GET /health (Cloud Run readiness probe)
│   │   ├── projects.py                 ← /projects routes
│   │   └── docs.py                     ← /projects/{id}/docs + /query routes
│   │
│   ├── types/                          ← Pydantic models (Tony's standard: /types not /models)
│   │   ├── __init__.py
│   │   ├── project.py                  ← ProjectCreate, ProjectResponse, ProjectListResponse
│   │   └── doc.py                      ← DocResponse, QueryRequest, QueryResponse, UploadResponse
│   │
│   └── streamlit/
│       ├── app.py                      ← Streamlit entry point
│       ├── api_client.py               ← Shared HTTP client — base URL + get/post/delete helpers
│       ├── components/
│       │   ├── __init__.py
│       │   ├── sidebar.py              ← Left pane: project list + new project dialog
│       │   └── progress.py             ← Upload pipeline progress display
│       └── pages/
│           ├── __init__.py
│           ├── dashboard.py            ← Diagnostics + maintenance dashboard
│           ├── corpus_manager.py       ← Page 1: doc list + delete
│           ├── upload.py               ← Page 2: drag-drop + pipeline status
│           └── qa_test.py              ← Page 3: multi-turn chat + sources
│
├── tests/
│   ├── __init__.py
│   ├── test_config_service.py          ← Unit tests: env loading + missing key errors
│   ├── test_state_service.py           ← Unit tests: projects.json CRUD + doc_count derivation
│   ├── test_rag_service.py             ← Unit tests: File Search API calls (fully mocked)
│   └── test_api.py                     ← Integration tests: all 9 FastAPI endpoints via httpx
│
├── uploads/                            ← Local staging folder for test docs
│   └── .gitkeep
├── logs/                               ← Runtime log directory (committed empty, log files ignored)
│   └── .gitkeep
│
├── main.py                             ← FastAPI app entry point (routers only)
├── projects.json                       ← State file (committed with empty state)
├── .env                                ← NOT committed
├── .env.example                        ← Committed — template only
├── .gitignore
├── requirements.txt
├── APP_BRIEF.md
├── CHANGELOG.md
├── DATA_CONTRACT.md
├── FILE_TREE.md
└── UI_SPEC.md
```

---

## File Responsibilities (What Lives Where)

### `src/services/config_service.py`

The **only** file that calls `os.getenv()` or loads `.env`.
All other modules import config values from this file.

Responsibilities:
- Load `.env` via `python-dotenv`
- Expose typed config values: `GEMINI_API_KEY`, `API_HOST`, `API_PORT`,
  `MAX_FILE_SIZE_MB`, `UPLOAD_TIMEOUT_SECONDS`, `SUMMARY_REQUIRED`
- Raise a clear `EnvironmentError` at startup if `GEMINI_API_KEY` is missing
- Never return `None` for required values — fail loudly at import time

### `src/services/logging_service.py`

The **only** file that configures logging.
All services import `logger` from this file — never call `logging.getLogger()` directly.

Responsibilities:
- Configure structured, timestamped logging
- Log level: `INFO` in normal operation, `DEBUG` when `LOG_LEVEL=debug` in `.env`
- All log entries include: timestamp, level, module name, message
- Errors include full exception traceback
- Never log API keys, file contents, or PII

### `src/services/rag_service.py`

The **only** file that imports `google.genai`.
All File Search API calls go here — no other file touches the Google SDK directly.

Responsibilities:
- Create / delete File Search stores
- Upload documents (async with polling — timeout enforced)
- Generate document summaries via Gemini
- Delete documents (always `config={'force': True}`)
- Query stores with the `file_search` tool
- Parse grounding metadata into source objects
- Enforce 90-second timeout on all polling operations

### `src/services/state_service.py`

The **only** file that reads/writes `projects.json`.
No other file touches the state file directly.

Responsibilities:
- Load and validate `projects.json` on startup
- CRUD operations for projects
- CRUD operations for docs within projects
- Atomic writes (read → modify → write)
- Auto-create `projects.json` if missing
- Always recalculate `doc_count = len(project["docs"])` after every mutation

### `src/api/health.py`

Single endpoint: `GET /health`

```python
@router.get("/health")
def health_check():
    return {"status": "ok"}
```

No auth required. No dependencies. Used for Cloud Run readiness probes.

### `src/api/projects.py`

FastAPI router for:
- `POST /projects`
- `GET /projects`
- `GET /projects/{id}`
- `DELETE /projects/{id}`

### `src/api/docs.py`

FastAPI router for:
- `POST /projects/{id}/upload`
- `GET /projects/{id}/docs`
- `DELETE /projects/{id}/docs/{doc_id}`
- `POST /projects/{id}/query`

### `src/api/diagnostics.py`

FastAPI router for diagnostics and maintenance:
- `GET /projects/{id}/store/check`
- `GET /projects/{id}/store/details`
- `GET /projects/{id}/store/documents`
- `GET /projects/{id}/store/documents/{document_name}`
- `GET /stores/verify`
- `POST /projects/{id}/store/cleanup-preview`
- `POST /projects/{id}/store/cleanup`
- `GET /operations/{operation_name}`

### `src/types/`

Pydantic v2 models only. No business logic. No API calls. Pure data shapes.
Import path: `from src.types.project import ProjectCreate`
Import path: `from src.types.doc import QueryRequest, QueryResponse`

**Note:** This folder is named `types/` — Tony's standard for all data shapes
and interfaces. Never rename to `models/`.

### `src/streamlit/api_client.py`

Shared HTTP client used by all Streamlit pages.
Base URL loaded from env: `API_BASE_URL` (default: `http://127.0.0.1:8000`).
Provides: `get()`, `post()`, `delete()` helpers.
Handles `ConnectionError` — returns structured error so pages can display
a consistent "API unreachable" message.

### `src/streamlit/app.py`

Entry point only. Sets page config, initializes session state, renders sidebar,
routes to active page via `st.tabs`.
No business logic. No direct API calls.

### `src/streamlit/pages/`

Each page component calls FastAPI via `api_client.py` — never imports from `src/services/`.
This is non-negotiable. Streamlit is a client. Period.

### `logs/`

Root-level runtime logging directory.
- Commit `logs/.gitkeep`
- Ignore `logs/*.log`
- Log format: `timestamp | level | module | message`

### `main.py`

```python
from fastapi import FastAPI
from src.api.health import router as health_router
from src.api.projects import router as projects_router
from src.api.docs import router as docs_router

app = FastAPI(title="Stark RAG API", version="1.0.0")
app.include_router(health_router)
app.include_router(projects_router)
app.include_router(docs_router)
```

Nothing else in `main.py`.

---

## `requirements.txt` (Exact Pins)

```
fastapi==0.115.0
uvicorn==0.30.6
google-genai==1.55.0
python-dotenv==1.0.1
pydantic==2.9.2
python-multipart==0.0.9
streamlit==1.39.0
requests==2.32.3
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.28.1
```

---

## `.env.example`

```bash
# Google Studio API Key (required)
# Get from: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_key_here

# FastAPI server (optional — defaults shown)
API_HOST=127.0.0.1
API_PORT=8000

# Upload configuration (optional)
MAX_FILE_SIZE_MB=50
UPLOAD_TIMEOUT_SECONDS=90

# Pipeline behavior (optional)
# Set to false to fall back to original-only upload if summary generation fails
SUMMARY_REQUIRED=true

# Logging (optional)
LOG_LEVEL=info
```

---

## `projects.json` (Initial Committed State)

```json
{
  "projects": {}
}
```

---

## `.gitignore` (Minimum)

```
.env
__pycache__/
*.pyc
.pytest_cache/
uploads/*.pdf
uploads/*.txt
.venv/
venv/
*.egg-info/
```

Note: `uploads/.gitkeep` stays committed. Actual uploaded files are ignored.

---

## How to Run

### Backend
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Streamlit
```bash
streamlit run src/streamlit/app.py
```

### Tests
```bash
pytest tests/ -v
```

All three commands must work in a clean venv after `pip install -r requirements.txt`.

---

## Codex Operating Rules for This Repo

1. Read `reference/patterns.md` before writing ANY File Search API call.
2. Read `reference/decisions.md` before making any architectural decision.
3. Do not modify anything in `reference/` — it is read-only.
4. Do not add files not listed in this tree without approval.
5. Do not bypass the service layer — Streamlit calls HTTP, period.
6. Run `pytest tests/ -v` after every module and confirm pass before moving on.
7. Write the DATA_CONTRACT shapes exactly — no field additions, no renames.
8. Always use `force=True` when deleting documents from File Search stores.
9. Always poll `operation.done` after upload — enforce 90-second timeout.
10. Keep `main.py` minimal — routers only, nothing else.
11. All env vars via `config_service.py` — never call `os.getenv()` directly.
12. All logging via `logging_service.py` — never call `logging.getLogger()` directly.
13. `doc_count` is always derived: `len(project["docs"])` — never manually set.
14. `status` must be exactly: `"processing"`, `"indexed"`, or `"failed"` — nothing else.
15. Folder is `src/types/` — never `src/models/`.

---

*Part of the Stark Industries AI Factory — managed-rag-api-v1*
*Version 1.2 | 2026-03-07*
