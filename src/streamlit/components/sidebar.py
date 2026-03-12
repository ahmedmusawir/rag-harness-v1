import streamlit as st

from src.streamlit import api_client


def _load_projects() -> list[dict[str, object]]:
    response = api_client.get("/projects")
    if response.status_code != 200:
        return []
    payload = response.json()
    return payload.get("projects", [])


@st.dialog("Create New Project")
def _new_project_dialog() -> None:
    name = st.text_input(
        "Project Name",
        placeholder="e.g. Architect Agent",
        max_chars=100,
    )
    description = st.text_area(
        "Description (optional)",
        placeholder="What is this agent for?",
        max_chars=500,
        height=100,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Create", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Project name is required.")
                return

            with st.spinner("Creating project..."):
                try:
                    response = api_client.post(
                        "/projects",
                        json={
                            "name": name.strip(),
                            "description": description.strip(),
                        },
                    )
                except ConnectionError:
                    st.error("Cannot reach API. Is the server running on port 8000?")
                    return

            if response.status_code == 201:
                data = response.json()
                st.session_state.active_project_id = data["id"]
                st.session_state.active_project_name = data["name"]
                st.session_state.corpus_needs_refresh = True
                st.session_state.projects = _load_projects()
                st.rerun()

            st.error(f"Failed: {response.json().get('detail', 'Unknown error')}")
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


def render_sidebar() -> None:
    with st.sidebar:
        try:
            health_response = api_client.get("/health")
            st.session_state.api_healthy = health_response.status_code == 200
        except ConnectionError:
            st.session_state.api_healthy = False

        try:
            st.session_state.projects = _load_projects()
        except ConnectionError:
            st.session_state.projects = []

        if st.button("+ New Project", use_container_width=True, type="primary"):
            _new_project_dialog()

        projects = st.session_state.projects
        if st.session_state.api_healthy is False:
            st.error("API unreachable")
            st.caption("Start FastAPI on port 8000, then refresh Streamlit.")

        if not projects:
            st.caption("No projects yet. Create one above.")
            st.session_state.active_project_id = None
            st.session_state.active_project_name = None
            return

        project_ids = [project["id"] for project in projects]
        project_lookup = {project["id"]: project for project in projects}

        active_id = st.session_state.active_project_id
        if active_id not in project_lookup:
            active_id = project_ids[0]
            st.session_state.active_project_id = active_id
            st.session_state.active_project_name = project_lookup[active_id]["name"]

        selected_id = st.radio(
            "Projects",
            options=project_ids,
            index=project_ids.index(active_id),
            format_func=lambda project_id: (
                f"{project_lookup[project_id]['name']} [{project_lookup[project_id]['doc_count']}]"
            ),
            label_visibility="collapsed",
        )

        if selected_id != st.session_state.active_project_id:
            st.session_state.active_project_id = selected_id
            st.session_state.active_project_name = project_lookup[selected_id]["name"]
            st.session_state.qa_messages = []
            st.session_state.selected_docs = []
            st.session_state.corpus_needs_refresh = True
            st.rerun()
