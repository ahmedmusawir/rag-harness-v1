import streamlit as st

from src.streamlit import api_client
from src.streamlit.components.progress import render_progress

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}


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

    uploaded_file = st.file_uploader(
        label="Upload a document",
        type=["pdf", "txt"],
        accept_multiple_files=False,
        help="Accepted: PDF, TXT. Max 50MB.",
        label_visibility="collapsed",
    )

    if uploaded_file is None:
        return

    if st.button("Start Upload", type="primary", use_container_width=True):
        suffix = ""
        if "." in uploaded_file.name:
            suffix = f".{uploaded_file.name.rsplit('.', 1)[1].lower()}"

        expected_mime = ALLOWED_TYPES.get(suffix)
        if expected_mime is None or uploaded_file.type != expected_mime:
            st.session_state.upload_status = "error"
            st.session_state.upload_error = "File type not supported. Accepted: PDF, TXT"
            st.rerun()

        file_bytes = uploaded_file.getvalue()
        if len(file_bytes) > 50 * 1024 * 1024:
            st.session_state.upload_status = "error"
            st.session_state.upload_error = "File too large. Max 50MB."
            st.rerun()

        st.session_state.upload_status = "uploading"
        st.session_state.upload_error = None
        try:
            with st.spinner("Processing document — this may take 30-90 seconds..."):
                response = api_client.post(
                    f"/projects/{project_id}/upload",
                    files={
                        "file": (
                            uploaded_file.name,
                            file_bytes,
                            uploaded_file.type,
                        )
                    },
                )
        except ConnectionError:
            st.session_state.upload_status = "error"
            st.session_state.upload_error = (
                "Cannot reach API. Is the server running on port 8000?"
            )
            st.rerun()
            return

        if response.status_code == 200:
            st.session_state.upload_status = "done"
            st.session_state.upload_error = None
            st.session_state.corpus_needs_refresh = True
            st.success("✅ Document indexed and ready to query!")
            st.rerun()
            return

        if response.status_code == 504:
            message = "⏱ Upload timed out. Google API did not respond. Please try again."
        elif response.status_code == 400:
            message = f"❌ {_response_detail(response)}"
        else:
            message = f"❌ Upload failed: {_response_detail(response)}"

        st.session_state.upload_status = "error"
        st.session_state.upload_error = message
        st.rerun()
