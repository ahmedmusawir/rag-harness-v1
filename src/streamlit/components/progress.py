import streamlit as st


STATUS_TEXT = {
    "uploading": "Uploading...",
    "summarizing": "Generating summary...",
    "indexing": "Indexing...",
    "done": "Done \u2713",
    "error": "Upload failed",
}


def render_progress(status: str | None, error: str | None = None) -> None:
    if status is None and not error:
        return

    if error:
        st.error(error)
        return

    label = STATUS_TEXT.get(status or "", status or "")
    if status == "done":
        st.success(label)
    elif status == "error":
        st.error(label)
    else:
        st.info(label)
