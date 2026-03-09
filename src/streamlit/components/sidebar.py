import streamlit as st


def render_sidebar() -> None:
    with st.sidebar:
        st.button("+ New Project", use_container_width=True, disabled=True)
        st.caption("Sidebar wiring arrives in later steps.")
