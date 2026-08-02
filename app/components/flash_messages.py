import streamlit as st

from app.form_state import pop_flash_message


def render_flash_message() -> None:
    """Render and consume a one-shot flash message from session state."""
    flash = pop_flash_message(st.session_state)
    if flash is None:
        return
    message, level = flash
    if level == "success":
        st.success(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.error(message)
