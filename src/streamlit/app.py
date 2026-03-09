import streamlit as st

from src.streamlit.components.sidebar import render_sidebar
from src.streamlit.pages import corpus_manager, qa_test, upload

INITIAL_STATE = {
    "active_project_id": None,
    "active_project_name": None,
    "active_page": "corpus",
    "projects": [],
    "qa_messages": [],
    "upload_status": None,
    "upload_error": None,
    "selected_docs": [],
    "corpus_needs_refresh": False,
    "api_healthy": None,
}


def initialize_session_state() -> None:
    for key, value in INITIAL_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main() -> None:
    st.set_page_config(page_title="Stark RAG Dev Rig", layout="wide")
    initialize_session_state()
    render_sidebar()

    tab1, tab2, tab3 = st.tabs(["📁 Corpus Manager", "⬆️ Upload", "🔍 Q&A Test"])

    with tab1:
        corpus_manager.render()

    with tab2:
        upload.render()

    with tab3:
        qa_test.render()


if __name__ == "__main__":
    main()
