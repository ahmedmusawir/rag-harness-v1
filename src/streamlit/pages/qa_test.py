import streamlit as st

from src.streamlit import api_client


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


def _render_sources(sources: list[dict[str, object]], latency_ms: int | None = None) -> None:
    col1, col2 = st.columns([3, 1])
    with col1:
        label = f"\U0001f4ce {len(sources)} source(s) used"
        st.caption(label)
    with col2:
        if latency_ms is not None:
            st.caption(f"\u23f1 {latency_ms}ms")

    with st.expander(label, expanded=False):
        for index, source in enumerate(sources, 1):
            st.markdown(f"**{index}. {source.get('doc_name', 'Unknown source')}**")
            chunk_text = source.get("chunk_text", "")
            if chunk_text:
                st.caption(f"\"{chunk_text[:200]}...\"")
            st.divider()


def render() -> None:
    project_id = st.session_state.active_project_id
    if not project_id:
        st.info("Select a project from the sidebar to start testing.")
        return

    project_name = st.session_state.active_project_name
    docs: list[dict[str, object]]
    try:
        docs = _load_docs(project_id)
    except ConnectionError:
        st.error("Cannot reach API. Is the server running on port 8000?")
        return

    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader(f"\U0001f50d Q&A Test | Project: {project_name}")
    with col2:
        if st.button("Clear Chat", type="secondary", use_container_width=True):
            st.session_state.qa_messages = []
            st.rerun()

    if not docs:
        st.warning("No documents in this project. Upload some docs first.")
        return

    for msg in st.session_state.qa_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sources"):
                _render_sources(msg["sources"], msg.get("latency_ms"))

    prompt = st.chat_input("Ask a question about your documents...")
    if prompt:
        st.session_state.qa_messages.append(
            {
                "role": "user",
                "content": prompt,
                "sources": [],
            }
        )

        with st.spinner("Searching..."):
            try:
                response = api_client.post(
                    f"/projects/{project_id}/query",
                    json={
                        "question": prompt,
                        "model": "gemini-2.5-pro",
                    },
                )
            except ConnectionError:
                st.session_state.qa_messages.append(
                    {
                        "role": "assistant",
                        "content": "❌ Cannot reach API. Is the server running?",
                        "sources": [],
                    }
                )
                st.rerun()
                return

        if response.status_code == 200:
            data = response.json()
            st.session_state.qa_messages.append(
                {
                    "role": "assistant",
                    "content": data["answer"],
                    "sources": data.get("sources", []),
                    "latency_ms": data.get("latency_ms"),
                }
            )
        else:
            st.session_state.qa_messages.append(
                {
                    "role": "assistant",
                    "content": f"❌ Query failed: {_response_detail(response)}",
                    "sources": [],
                }
            )

        st.rerun()
