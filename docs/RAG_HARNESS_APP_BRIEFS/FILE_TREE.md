# File Tree: managed-rag-api-v1

> **Status:** 🔒 LOCKED
> **Version:** 1.0
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
│   │   ├── rag_service.py              ← All File Search API calls live here
│   │   └── state_service.py            ← projects.json read/write/validate
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── projects.py                 ← /projects routes
│   │   └── docs.py                     ← /projects/{id}/docs + /query routes
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── project.py                  ← Pydantic models: Project, ProjectCreate
│   │   └── doc.py                      ← Pydantic models: Doc, QueryRequest, QueryResponse
│   │
│   └── streamlit/
│       ├── app.py                      ← Streamlit entry point
│       ├── components/
│       │   ├── __init__.py
│       │   ├── sidebar.py              ← Left pane: project list + new project
│       │   └── progress.py             ← Upload pipeline progress display
│       └── pages/
│           ├── __init__.py
│           ├── corpus_manager.py       ← Page 1: doc list + delete
│           ├── upload.py               ← Page 2: drag-drop + pipeline status
│           └── qa_test.py              ← Page 3: multi-turn chat + sources
│
├── tests/
│   ├── __init__.py
│   ├── test_state_service.py           ← Unit tests: projects.json CRUD
│   ├── test_rag_service.py             ← Unit tests: File Search API calls (mocked)
│   └── test_api.py                     ← Integration tests: FastAPI endpoints
│
├── uploads/                            ← Local staging folder for test docs
│   └── .gitkeep
│
├── main.py                             ← FastAPI app entry point
├── projects.json                       ← State file (committed with empty state)
├── .env                                ← NOT committed
├── .env.example                        ← Committed — template only
├── .gitignore
├── requirements.txt
├── APP_BRIEF.md
├── DATA_CONTRACT.md
└── FILE_TREE.md
```

---

## File Responsibilities (What Lives Where)

### `src/services/rag_service.py`

The ONLY file that imports `google.genai`. All File Search API calls go here.
No other file touches the Google SDK directly.

Responsibilities:
- Create / delete File Search stores
- Upload documents (async with polling)
- Generate document summaries via Gemini
- Delete documents (always force=True)
- Query stores with the file_search tool
- Parse grounding metadata into source objects

### `src/services/state_service.py`

The ONLY file that reads/writes `projects.json`.
No other file touches the state file directly.

Responsibilities:
- Load and validate projects.json on startup
- CRUD operations for projects
- CRUD operations for docs within projects
- Atomic writes (read → modify → write)
- Auto-create projects.json if missing

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

### `src/models/`

Pydantic v2 models only. No business logic. No API calls. Pure data shapes.

### `src/streamlit/app.py`

Entry point only. Sets page config, renders sidebar, routes to active page.
No business logic. No direct API calls (uses `requests` via page components).

### `src/streamlit/pages/`

Each page component calls FastAPI via `requests` — never imports from `src/services/`.
This is non-negotiable. The Streamlit layer is a client, not a server.

### `main.py`

```python
from fastapi import FastAPI
from src.api.projects import router as projects_router
from src.api.docs import router as docs_router

app = FastAPI(title="Stark RAG API", version="1.0.0")
app.include_router(projects_router)
app.include_router(docs_router)
```

Nothing else in main.py.

---

## `requirements.txt` (Exact Pins)

```
fastapi==0.115.0
uvicorn==0.30.6
google-genai==1.55.0
python-dotenv==1.0.1
pydantic==2.8.2
python-multipart==0.0.9
streamlit==1.39.0
requests==2.32.3
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
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

# Upload limits (optional)
MAX_FILE_SIZE_MB=50
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
9. Always poll `operation.done` after upload — never assume instant indexing.
10. Keep `main.py` minimal — routers only, nothing else.

---

*Part of the Stark Industries AI Factory — managed-rag-api-v1*
*Version 1.0 | 2026-03-07*
