import streamlit as st
import pandas as pd

from src.streamlit import api_client


def _format_size(num_bytes: int) -> str:
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes} B"


def _status_label(status: str) -> str:
    return {
        "indexed": "Indexed",
        "processing": "Processing",
        "failed": "Failed",
    }.get(status, status)


def _load_project(project_id: str) -> dict[str, object] | None:
    response = api_client.get(f"/projects/{project_id}")
    if response.status_code != 200:
        return None
    return response.json()


def _response_payload(response):
    try:
        return response.json()
    except Exception:
        text = response.text.strip()
        return {"detail": text or f"HTTP {response.status_code}"}


def _set_result(title: str, payload: dict[str, object]) -> None:
    st.session_state.dashboard_result = {
        "title": title,
        "payload": payload,
    }
    st.session_state.health_check_result = None


def _show_resource(label: str, value: str) -> None:
    st.caption(label)
    st.code(value or "(empty)", language="text")


def _parse_health(health_resp, openapi_resp) -> dict:
    status = "ok" if health_resp.status_code == 200 else "error"
    rows = []
    try:
        spec = openapi_resp.json()
        method_order = {"get": 0, "post": 1, "delete": 2}
        for path, methods in sorted(spec.get("paths", {}).items()):
            for method, detail in methods.items():
                if method not in method_order:
                    continue
                rows.append({
                    "Method": method.upper(),
                    "Endpoint": path,
                    "Description": detail.get("summary", ""),
                })
        rows.sort(key=lambda r: (r["Endpoint"], method_order.get(r["Method"].lower(), 9)))
    except Exception:
        pass
    return {"status": status, "endpoints": rows}


def _render_health(data: dict) -> None:
    status = data.get("status", "error")
    if status == "ok":
        st.success("API Status: ok")
    else:
        st.error(f"API Status: {status}")

    rows = data.get("endpoints", [])
    if rows:
        st.markdown("**Registered Endpoints**")
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Method": st.column_config.TextColumn(width="small"),
                "Endpoint": st.column_config.TextColumn(width="medium"),
                "Description": st.column_config.TextColumn(width="large"),
            },
        )


def render() -> None:
    st.subheader("Dashboard")

    project_id = st.session_state.active_project_id
    if not project_id:
        st.info("Select a project from the sidebar to inspect the current store.")
        return

    try:
        project = _load_project(project_id)
    except ConnectionError:
        st.error("Cannot reach API. Is the server running on port 8000?")
        return

    if not project:
        st.warning("Project details are unavailable.")
        return

    docs_map = project.get("docs", {}) or {}
    docs = list(docs_map.values())
    indexed_count = sum(1 for doc in docs if doc.get("status") == "indexed")
    summary_count = sum(1 for doc in docs if doc.get("summary_doc_name"))

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Project", str(project.get("name", "")))
    metric2.metric("Docs", str(project.get("doc_count", 0)))
    metric3.metric("Indexed", str(indexed_count))
    metric4.metric("Summary Docs", str(summary_count))

    st.caption(f"Store: {project.get('store_id', '')}")
    st.caption(
        "Diagnostics view backed by API endpoints. Use the copy button on each code block for MCP/ADK tooling work."
    )

    st.markdown("### Store References")
    _show_resource("Store ID", str(project.get("store_id", "")))
    _show_resource("Project ID", str(project.get("id", project_id)))

    if not docs:
        st.info("No documents uploaded yet.")
    else:
        rows = []
        for doc in docs:
            rows.append(
                {
                    "filename": doc.get("original_name", ""),
                    "status": _status_label(str(doc.get("status", ""))),
                    "size": _format_size(int(doc.get("file_size_bytes", 0))),
                    "has_summary": "yes" if doc.get("summary_doc_name") else "no",
                    "store_doc": doc.get("store_doc_name", ""),
                    "summary_doc": doc.get("summary_doc_name", ""),
                }
            )

        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        st.markdown("### Document Resource Names")
        for doc in docs:
            with st.expander(doc.get("original_name", "Document"), expanded=False):
                _show_resource("Original document resource", str(doc.get("store_doc_name", "")))
                _show_resource("Summary document resource", str(doc.get("summary_doc_name", "")))

    st.markdown("### Diagnostics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Check Store", use_container_width=True):
            try:
                response = api_client.get(f"/projects/{project_id}/store/check")
                _set_result("Check Store", _response_payload(response))
            except ConnectionError:
                st.error("Cannot reach API. Is the server running on port 8000?")
    with col2:
        if st.button("Get Store Details", use_container_width=True):
            try:
                response = api_client.get(f"/projects/{project_id}/store/details")
                _set_result("Get Store Details", _response_payload(response))
            except ConnectionError:
                st.error("Cannot reach API. Is the server running on port 8000?")
    with col3:
        if st.button("Verify All Stores", use_container_width=True):
            try:
                response = api_client.get("/stores/verify", timeout=120)
                _set_result("Verify All Stores", _response_payload(response))
            except ConnectionError:
                st.error("Cannot reach API. Is the server running on port 8000?")
    with col4:
        if st.button("Health Check", use_container_width=True):
            try:
                health_resp = api_client.get("/health")
                openapi_resp = api_client.get("/openapi.json")
                st.session_state.health_check_result = _parse_health(health_resp, openapi_resp)
                st.session_state.dashboard_result = None
            except ConnectionError:
                st.error("Cannot reach API. Is the server running on port 8000?")

    doc_options = {
        f"{doc.get('original_name', 'Unnamed')}": str(doc.get("store_doc_name", ""))
        for doc in docs
        if doc.get("store_doc_name")
    }
    st.markdown("### Document Details")
    selected_doc_label = st.selectbox(
        "Select a document resource",
        options=list(doc_options.keys()) if doc_options else ["No document resources available"],
        disabled=not doc_options,
    )
    if doc_options and st.button("Get Document Details", use_container_width=True):
        try:
            response = api_client.get(
                f"/projects/{project_id}/store/documents/{doc_options[selected_doc_label]}"
            )
            _set_result("Get Document Details", _response_payload(response))
        except ConnectionError:
            st.error("Cannot reach API. Is the server running on port 8000?")

    st.markdown("### Cleanup Store")
    st.warning(
        "Cleanup Store will delete all documents from the selected Google store, clear this project's docs from app state, and leave the project/store record intact."
    )
    if st.button("Preview Cleanup", type="secondary", use_container_width=True):
        try:
            response = api_client.post(f"/projects/{project_id}/store/cleanup-preview")
            st.session_state.cleanup_preview = _response_payload(response)
        except ConnectionError:
            st.error("Cannot reach API. Is the server running on port 8000?")

    preview = st.session_state.cleanup_preview
    if preview and preview.get("project_id") == project_id:
        st.json(preview)
        confirmation_text = st.text_input(
            "Type EMPTY STORE to confirm cleanup",
            value="",
            key=f"cleanup_confirm_{project_id}",
        )
        col_confirm, col_cancel = st.columns(2)
        with col_confirm:
            if st.button("Execute Cleanup Store", type="primary", use_container_width=True):
                try:
                    response = api_client.post(
                        f"/projects/{project_id}/store/cleanup",
                        json={
                            "confirm": True,
                            "confirmation_text": confirmation_text,
                        },
                    )
                    payload = _response_payload(response)
                    _set_result("Cleanup Store", payload)
                    if response.status_code == 200:
                        st.session_state.cleanup_preview = None
                        st.session_state.corpus_needs_refresh = True
                        st.success(payload.get("message", "Store cleaned successfully."))
                        st.rerun()
                    else:
                        st.error(payload.get("detail", "Cleanup failed."))
                except ConnectionError:
                    st.error("Cannot reach API. Is the server running on port 8000?")
        with col_cancel:
            if st.button("Cancel Cleanup", use_container_width=True):
                st.session_state.cleanup_preview = None
                st.rerun()

    health = st.session_state.health_check_result
    if health:
        st.markdown("### Health Check")
        _render_health(health)

    result = st.session_state.dashboard_result
    if result:
        st.markdown("### Latest Diagnostics Result")
        st.caption(result["title"])
        st.json(result["payload"])
