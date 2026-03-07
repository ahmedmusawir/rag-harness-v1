# UI_SPEC: managed-rag-api-v1 Streamlit Dev Rig

> **Status:** 🔒 LOCKED
> **Version:** 1.0
> **Date:** 2026-03-07
> **Audience:** Codex (Engineer Agent)
> **Replaces:** Designer Agent + Stitch (not needed for dev rig)

---

## 1. Design Philosophy

This is a **developer tool**, not a consumer product.

| Principle | Implementation |
|-----------|---------------|
| Utility first | Dense information, no decorative elements |
| Dark theme | `st.set_page_config(layout="wide")` + dark Streamlit theme |
| Feedback always | Every action has a visible result (spinner, badge, toast) |
| API-first | Every button triggers an HTTP call — no direct Python imports from src/ |
| Supabase dashboard aesthetic | Clean, monospaced where appropriate, status badges |

---

## 2. Global Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  SIDEBAR (always visible)    │  MAIN CONTENT AREA               │
│  width: ~280px               │  (fills remaining width)         │
│                              │                                  │
│  [ + New Project ]           │  ┌──────────────────────────┐   │
│  ─────────────────           │  │  NAV TABS                │   │
│  ● Architect Agent    [3]    │  │  Corpus | Upload | Q&A   │   │
│    Engineer Agent     [7]    │  └──────────────────────────┘   │
│    GHL Docs           [12]   │                                  │
│    ...                       │  [Active page content here]      │
│                              │                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Sidebar Rules
- Use `st.sidebar` for the full left pane
- "New Project" button at the very top, full width, primary color
- Project list rendered as `st.radio` or `st.button` list — one item per project
- Active project highlighted (use `st.session_state.active_project_id`)
- Doc count shown as `[N]` badge next to each project name
- If no projects exist: show "No projects yet. Create one above." in muted text
- Sidebar always visible regardless of active page

---

## 3. Session State Schema

Codex must initialize ALL session state keys at app startup in `app.py`.
Never access `st.session_state` without checking existence first.

```python
# Initialized in app.py on first load
INITIAL_STATE = {
    "active_project_id": None,        # str | None
    "active_project_name": None,      # str | None
    "active_page": "corpus",          # "corpus" | "upload" | "qa"
    "projects": [],                   # list of project dicts from GET /projects
    "qa_messages": [],                # list of {"role": "user"|"assistant", "content": str, "sources": []}
    "upload_status": None,            # None | "uploading" | "summarizing" | "indexing" | "done" | "error"
    "upload_error": None,             # str | None
    "selected_docs": [],              # list of doc_ids selected in corpus manager
}
```

---

## 4. Navigation

Use `st.tabs` inside the main area for the three pages.
Do NOT use `st.page_link` or multi-page Streamlit app structure.
Everything lives in `app.py` — pages are components rendered conditionally.

```python
tab1, tab2, tab3 = st.tabs(["📁 Corpus Manager", "⬆️ Upload", "🔍 Q&A Test"])

with tab1:
    from src.streamlit.pages.corpus_manager import render
    render()

with tab2:
    from src.streamlit.pages.upload import render
    render()

with tab3:
    from src.streamlit.pages.qa_test import render
    render()
```

---

## 5. Page Spec: Corpus Manager

**File:** `src/streamlit/pages/corpus_manager.py`
**Function:** `render()`

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│  📁 Corpus Manager                                           │
│  Project: Architect Agent  |  Store: fileSearchStores/...    │
├──────────────────────────────────────────────────────────────┤
│  [ 🗑 Delete Selected ]  [ ↻ Refresh ]          3 documents  │
├──────────────────────────────────────────────────────────────┤
│  ☐  │ Filename              │ Size    │ Uploaded    │ Status │
│─────┼───────────────────────┼─────────┼─────────────┼────────│
│  ☑  │ APP_ARCHITECTURE_...  │ 240 KB  │ Mar 07 14:35│ ✅     │
│  ☐  │ API_AND_SERVICES_...  │ 180 KB  │ Mar 07 14:36│ ✅     │
│  ☐  │ ENGINEER_PLAYBOOK...  │ 95 KB   │ Mar 07 14:37│ ⏳     │
└──────────────────────────────────────────────────────────────┘
```

### Behavior Rules

**No project selected:**
Show: `st.info("Select a project from the sidebar to view its documents.")`

**Project selected, no docs:**
Show: `st.info("No documents yet. Go to Upload to add your first doc.")`

**Project selected, docs exist:**
- Render table using `st.data_editor` with a checkbox column
- Columns: `select (bool)`, `filename`, `size`, `uploaded`, `status`
- Status badges:
  - `indexed` → `✅ Indexed`
  - `processing` → `⏳ Processing`
  - `failed` → `❌ Failed`
- File size: display as KB or MB (auto-format, never raw bytes)
- Uploaded: display as `Mar 07 14:35` format (not full ISO)

**Delete Selected button:**
- Disabled if no checkboxes selected
- On click: show `st.warning("Delete N selected document(s)? This cannot be undone.")`
- Confirm with `st.button("Confirm Delete")`
- On confirm: call `DELETE /projects/{id}/docs/{doc_id}` for each selected doc
- Show `st.spinner("Deleting...")` during calls
- On success: `st.success("Deleted N document(s).")` + refresh doc list
- On failure: `st.error("Failed to delete: {error}")`

**Refresh button:**
- Re-calls `GET /projects/{id}/docs`
- No spinner needed — fast operation

**Auto-refresh:**
- After any upload completes (triggered via session state flag)
- Do NOT use `st.rerun()` in a loop — only trigger once after state change

---

## 6. Page Spec: Upload

**File:** `src/streamlit/pages/upload.py`
**Function:** `render()`

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│  ⬆️ Upload Documents                                         │
│  Project: Architect Agent                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │                                                      │   │
│   │        Drag and drop files here                      │   │
│   │        or click to browse                            │   │
│   │                                                      │   │
│   │        Accepted: PDF, TXT  │  Max: 50MB each         │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
│  [pipeline status area — shown during/after upload]          │
└──────────────────────────────────────────────────────────────┘
```

### File Uploader

```python
uploaded_file = st.file_uploader(
    label="",
    type=["pdf", "txt"],
    accept_multiple_files=False,   # one at a time
    help="Accepted: PDF, TXT. Max 50MB."
)
```

**One file at a time.** No batch upload in v1.

### Validation (Before Upload)

Check before calling the API:
- File type: only `application/pdf` or `text/plain`
- File size: reject if > 50MB, show `st.error("File too large. Max 50MB.")`
- Project selected: if none, show `st.warning("Select a project first.")`

### Pipeline Progress Display

When upload starts, show a 4-step progress flow:

```python
# Use st.status() for multi-step display
with st.status("Processing document...", expanded=True) as status:
    st.write("📤 Uploading file...")
    # ... after file sent to API ...
    st.write("🧠 Generating summary...")
    # ... after summary step ...
    st.write("📦 Indexing in RAG store...")
    # ... after indexing complete ...
    st.write("✅ Done!")
    status.update(label="Document ready!", state="complete")
```

**Status labels (exact text):**
1. `"📤 Uploading file..."`
2. `"🧠 Generating summary..."`
3. `"📦 Indexing in RAG store..."`
4. `"✅ Done! Document is ready to query."`

**Note:** Since the FastAPI endpoint is synchronous (returns only after full pipeline),
the Streamlit side shows a single spinner during the HTTP call, then updates all steps
to complete on success. Do not fake step-by-step progress unless the API supports it.

**Actual implementation:**
```python
with st.spinner("Processing document — this may take 30-60 seconds..."):
    response = requests.post(f"{API_BASE}/projects/{project_id}/upload", files=...)

if response.status_code == 200:
    st.success("✅ Document indexed and ready to query!")
    st.session_state.corpus_needs_refresh = True
else:
    st.error(f"Upload failed: {response.json().get('detail', 'Unknown error')}")
```

### Post-Upload

- Show success message with doc name
- Set `st.session_state.corpus_needs_refresh = True`
- Clear the file uploader (via `st.rerun()` after state update)
- Do NOT auto-navigate to Corpus Manager — let the user decide

---

## 7. Page Spec: Q&A Test

**File:** `src/streamlit/pages/qa_test.py`
**Function:** `render()`

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│  🔍 Q&A Test  │  Project: Architect Agent  [ Clear Chat ]    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 🧑 What is the service layer pattern?                  │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 🤖 The service layer pattern enforces a strict         │  │
│  │    separation between UI components and data...        │  │
│  │                                                        │  │
│  │  📎 Sources:                                           │  │
│  │  • API_AND_SERVICES_MANUAL — "Components render.       │  │
│  │    Services fetch..."                                  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Ask a question about your documents...          [Send]│  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Chat Implementation

```python
# Render conversation history
for msg in st.session_state.qa_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            render_sources(msg["sources"])

# Input
if prompt := st.chat_input("Ask a question about your documents..."):
    # Add user message immediately
    st.session_state.qa_messages.append({
        "role": "user",
        "content": prompt,
        "sources": []
    })

    # Call API
    with st.spinner("Searching..."):
        response = requests.post(
            f"{API_BASE}/projects/{project_id}/query",
            json={"question": prompt}
        )

    if response.status_code == 200:
        data = response.json()
        st.session_state.qa_messages.append({
            "role": "assistant",
            "content": data["answer"],
            "sources": data.get("sources", [])
        })
    else:
        st.session_state.qa_messages.append({
            "role": "assistant",
            "content": f"❌ Query failed: {response.json().get('detail', 'Unknown error')}",
            "sources": []
        })

    st.rerun()
```

### Sources Display

```python
def render_sources(sources: list):
    if not sources:
        return
    with st.expander(f"📎 {len(sources)} source(s) used", expanded=False):
        for i, source in enumerate(sources, 1):
            st.markdown(f"**{i}. {source['doc_name']}**")
            if source.get("chunk_text"):
                st.caption(f'"{source["chunk_text"][:200]}..."')
            st.divider()
```

### Behavior Rules

**No project selected:**
Show: `st.info("Select a project from the sidebar to start testing.")`

**Project selected, no docs:**
Show: `st.warning("No documents in this project. Upload some docs first.")`

**Project selected, docs exist:**
- Render full chat interface
- `st.chat_input` always visible at the bottom
- Sources collapsed by default (use `st.expander`)
- Conversation lives in `st.session_state.qa_messages` — not persisted

**Clear Chat button:**
```python
if st.button("Clear Chat", type="secondary"):
    st.session_state.qa_messages = []
    st.rerun()
```

---

## 8. New Project Modal

Triggered by "New Project" button in sidebar.
Use `st.dialog` (Streamlit 1.36+) or fallback to sidebar form.

```python
@st.dialog("Create New Project")
def new_project_dialog():
    name = st.text_input(
        "Project Name",
        placeholder="e.g. Architect Agent",
        max_chars=100
    )
    description = st.text_area(
        "Description (optional)",
        placeholder="What is this agent for?",
        max_chars=500,
        height=100
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Create", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Project name is required.")
            else:
                with st.spinner("Creating project..."):
                    response = requests.post(
                        f"{API_BASE}/projects",
                        json={"name": name.strip(), "description": description.strip()}
                    )
                if response.status_code == 201:
                    st.session_state.active_project_id = response.json()["id"]
                    st.session_state.active_project_name = response.json()["name"]
                    st.rerun()
                else:
                    st.error(f"Failed: {response.json().get('detail')}")
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
```

---

## 9. API Client Config

All Streamlit pages use a shared base URL from env or default:

```python
# src/streamlit/api_client.py
import os
import requests

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

def get(endpoint: str) -> requests.Response:
    return requests.get(f"{API_BASE}{endpoint}")

def post(endpoint: str, **kwargs) -> requests.Response:
    return requests.post(f"{API_BASE}{endpoint}", **kwargs)

def delete(endpoint: str) -> requests.Response:
    return requests.delete(f"{API_BASE}{endpoint}")
```

All pages import from `api_client.py` — never hardcode the base URL.

---

## 10. Streamlit App Config

`src/streamlit/app.py` must set this at the very top:

```python
st.set_page_config(
    page_title="Stark RAG Studio",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)
```

App title in sidebar header:
```python
st.sidebar.title("🔧 Stark RAG Studio")
st.sidebar.caption("AI Factory — Layer 3 RAG Manager")
```

---

## 11. Gating Logic (Human Checkpoints)

These are the states where the UI must block and guide the user:

| State | Condition | UI Response |
|-------|-----------|-------------|
| No project selected | `active_project_id is None` | `st.info()` on all 3 pages |
| No docs in project | `doc_count == 0` on Q&A page | `st.warning()` to go upload |
| Upload in progress | `upload_status == "uploading"` | Disable upload button |
| Doc still processing | `status == "processing"` | Show ⏳ badge, disable query |
| API unreachable | Connection error on any call | `st.error("Cannot reach API. Is the server running?")` |

---

## 12. File Uploader Note for Codex

Streamlit's `st.file_uploader` returns a `UploadedFile` object.
Send it to FastAPI as multipart form data like this:

```python
files = {
    "file": (
        uploaded_file.name,
        uploaded_file.getvalue(),
        uploaded_file.type
    )
}
response = requests.post(
    f"{API_BASE}/projects/{project_id}/upload",
    files=files
)
```

Do NOT use `uploaded_file.read()` — use `.getvalue()` to support re-reads.

---

## 13. Error Handling (All Pages)

| Error Type | Display Method |
|------------|---------------|
| Validation error | `st.error()` inline near the input |
| API 404 | `st.warning("Project or document not found.")` |
| API 500 | `st.error("Server error: {detail}")` |
| Network error | `st.error("Cannot reach API. Is the server running on port 8000?")` |
| Empty response | `st.warning("No data returned.")` |

Never show raw stack traces to the user.
Always wrap API calls in try/except and handle `requests.exceptions.ConnectionError`.

---

## 14. Success Definition for UI

1. Sidebar shows project list populated from `GET /projects` on load
2. Creating a project makes it appear in sidebar immediately
3. Upload flow shows spinner during processing and success message on completion
4. Corpus Manager shows doc list with correct status badges
5. Delete with confirmation works and removes doc from list
6. Q&A page shows multi-turn conversation with sources collapsed under each answer
7. Switching projects clears Q&A history and refreshes doc list
8. API unreachable state shows clear error on all pages

---

*Part of the Stark Industries AI Factory — managed-rag-api-v1*
*Version 1.0 | 2026-03-07*
