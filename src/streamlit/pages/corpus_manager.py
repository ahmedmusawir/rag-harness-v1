import streamlit as st
import pandas as pd

from src.streamlit import api_client


def _format_size(num_bytes: int) -> str:
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes} B"


def _format_uploaded(timestamp: str) -> str:
    if not timestamp:
        return ""
    cleaned = timestamp.replace("Z", "+00:00")
    try:
        return pd.Timestamp(cleaned).strftime("%b %d %H:%M")
    except Exception:
        return timestamp


def _status_label(status: str) -> str:
    return {
        "indexed": "\u2705 Indexed",
        "processing": "\u23f3 Processing",
        "failed": "\u274c Failed",
    }.get(status, status)


def _load_docs(project_id: str) -> list[dict[str, object]]:
    response = api_client.get(f"/projects/{project_id}/docs")
    if response.status_code != 200:
        return []
    return response.json().get("docs", [])


def _response_detail(response) -> str:
    try:
        payload = response.json()
        return payload.get("detail", "Unknown error")
    except Exception:
        text = response.text.strip()
        return text or f"HTTP {response.status_code}"


def render() -> None:
    st.subheader("\U0001f4c1 Corpus Manager")

    project_id = st.session_state.active_project_id
    if not project_id:
        st.info("Select a project from the sidebar to view its documents.")
        return

    project = next(
        (item for item in st.session_state.projects if item["id"] == project_id),
        None,
    )
    if project is None:
        st.info("Select a project from the sidebar to view its documents.")
        return

    st.caption(
        f"Project: {project['name']} | Store: {project['store_id']}"
    )

    try:
        docs = _load_docs(project_id)
    except ConnectionError:
        st.error("Cannot reach API. Is the server running on port 8000?")
        return

    if st.session_state.corpus_needs_refresh:
        st.session_state.corpus_needs_refresh = False

    selected_ids = st.session_state.selected_docs
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        delete_clicked = st.button(
            "\U0001f5d1 Delete Selected",
            disabled=not selected_ids,
        )
    with col2:
        refresh_clicked = st.button("\u21bb Refresh")
    with col3:
        st.caption(f"{len(docs)} documents")

    if refresh_clicked:
        st.session_state.corpus_needs_refresh = False
        st.rerun()

    if not docs:
        st.session_state.selected_docs = []
        st.info("No documents yet. Go to Upload to add your first doc.")
        return

    rows = [
        {
            "select": doc["id"] in selected_ids,
            "filename": doc["original_name"],
            "size": _format_size(int(doc["file_size_bytes"])),
            "uploaded": _format_uploaded(doc["uploaded_at"]),
            "status": _status_label(doc["status"]),
        }
        for doc in docs
    ]
    editor_df = pd.DataFrame(rows)

    edited = st.data_editor(
        editor_df,
        hide_index=True,
        use_container_width=True,
        disabled=["filename", "size", "uploaded", "status"],
        column_config={
            "select": st.column_config.CheckboxColumn("select"),
            "filename": st.column_config.TextColumn("filename"),
            "size": st.column_config.TextColumn("size"),
            "uploaded": st.column_config.TextColumn("uploaded"),
            "status": st.column_config.TextColumn("status"),
        },
    )
    st.session_state.selected_docs = [
        docs[index]["id"]
        for index, selected in enumerate(edited["select"].tolist())
        if selected
    ]

    if delete_clicked and st.session_state.selected_docs:
        st.session_state.pending_delete = True

    if st.session_state.pending_delete and st.session_state.selected_docs:
        count = len(st.session_state.selected_docs)
        st.warning(f"Delete {count} selected document(s)? This cannot be undone.")
        col_confirm, col_cancel = st.columns(2)
        with col_confirm:
            confirm_delete = st.button("Confirm Delete", type="primary")
        with col_cancel:
            cancel_delete = st.button("Cancel Delete")

        if cancel_delete:
            st.session_state.pending_delete = False
            st.rerun()

        if confirm_delete:
            try:
                with st.spinner("Deleting..."):
                    for doc_id in st.session_state.selected_docs:
                        response = api_client.delete(f"/projects/{project_id}/docs/{doc_id}")
                        if response.status_code != 200:
                            detail = _response_detail(response)
                            st.error(f"Failed to delete: {detail}")
                            st.session_state.pending_delete = False
                            return
            except ConnectionError:
                st.error("Cannot reach API. Is the server running on port 8000?")
                st.session_state.pending_delete = False
                return

            st.session_state.selected_docs = []
            st.session_state.pending_delete = False
            st.session_state.corpus_needs_refresh = True
            st.success(f"Deleted {count} document(s).")
            st.rerun()
