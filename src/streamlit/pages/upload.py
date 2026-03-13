import streamlit as st

from src.streamlit import api_client
from src.streamlit.components.progress import render_progress


def _response_detail(response) -> str:
    try:
        payload = response.json()
        return payload.get("detail", "Unknown error")
    except Exception:
        text = response.text.strip()
        return text or f"HTTP {response.status_code}"


def render() -> None:
    st.subheader("\u2b06\ufe0f Upload Documents")

    project_id = st.session_state.active_project_id
    project_name = st.session_state.active_project_name
    if not project_id:
        st.warning("Select a project first.")
        return

    st.caption(f"Project: {project_name}")
    render_progress(st.session_state.upload_status, st.session_state.upload_error)

    uploaded_files = st.file_uploader(
        label="Upload documents",
        type=None,
        accept_multiple_files=True,
        help="Accepted: PDF, DOCX, XLSX, PPTX, TXT, CSV, MD, HTML, JSON, RTF. Max 50MB.",
        label_visibility="collapsed",
    )

    if not uploaded_files:
        return

    if st.button("Start Upload", type="primary", use_container_width=True):
        results = {"success": [], "failed": []}
        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.getvalue()
            if len(file_bytes) > 50 * 1024 * 1024:
                results["failed"].append(f"{uploaded_file.name}: file too large (max 50MB)")
                continue

            try:
                with st.spinner(f"Processing {uploaded_file.name} — this may take 30-90 seconds..."):
                    response = api_client.post(
                        f"/projects/{project_id}/upload",
                        files={"file": (uploaded_file.name, file_bytes, uploaded_file.type)},
                    )
            except ConnectionError:
                st.session_state.upload_status = "error"
                st.session_state.upload_error = "Cannot reach API. Is the server running on port 8000?"
                st.rerun()
                return

            if response.status_code == 200:
                results["success"].append(uploaded_file.name)
                st.session_state.corpus_needs_refresh = True
            elif response.status_code == 504:
                results["failed"].append(f"{uploaded_file.name}: upload timed out")
            else:
                results["failed"].append(f"{uploaded_file.name}: {_response_detail(response)}")

        if results["success"]:
            st.session_state.upload_status = "done"
            st.session_state.upload_error = None
            st.success(f"✅ {len(results['success'])} document(s) indexed: {', '.join(results['success'])}")
        if results["failed"]:
            st.session_state.upload_status = "error"
            st.session_state.upload_error = "\n".join(results["failed"])
        st.rerun()
