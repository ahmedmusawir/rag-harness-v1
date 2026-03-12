import streamlit as st

from src.streamlit.components.sidebar import render_sidebar
from src.streamlit.pages import corpus_manager, dashboard, qa_test, upload

INITIAL_STATE = {
    "active_project_id": None,
    "active_project_name": None,
    "active_page": "dashboard",
    "projects": [],
    "qa_messages": [],
    "upload_status": None,
    "upload_error": None,
    "selected_docs": [],
    "corpus_needs_refresh": False,
    "api_healthy": None,
    "pending_delete": False,
    "dashboard_result": None,
    "cleanup_preview": None,
}


def initialize_session_state() -> None:
    for key, value in INITIAL_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main() -> None:
    st.set_page_config(page_title="Stark RAG Dev Rig", layout="wide")
    initialize_session_state()
    render_sidebar()

    st.title("Stark RAG Dev Rig")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Dashboard", "📁 Corpus Manager", "⬆️ Upload", "🔍 Q&A Test"]
    )

    with tab1:
        dashboard.render()

    with tab2:
        corpus_manager.render()

    with tab3:
        upload.render()

    with tab4:
        qa_test.render()


if __name__ == "__main__":
    main()
