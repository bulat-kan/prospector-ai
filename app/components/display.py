from typing import Optional

import streamlit as st

from app.constants import LEAD_SOURCE_AE_FOUND, LEAD_SOURCE_LABELS, LEAD_SOURCE_REFERRAL
from app.enums import ContactRole
from app.ui_helpers import friendly_label
from app.validation import contact_display_name


def show_crud_message(error: Exception) -> None:
    st.error(str(error))


def lead_source_options() -> list[Optional[str]]:
    return [None, LEAD_SOURCE_AE_FOUND, LEAD_SOURCE_REFERRAL]


def lead_source_label(value: Optional[str]) -> str:
    if value is None:
        return "Not set"
    return LEAD_SOURCE_LABELS.get(value, friendly_label(value))


def contact_name_label(first_name: Optional[str], last_name: Optional[str]) -> str:
    return contact_display_name(first_name, last_name)


def decision_role_value_label(value: str) -> str:
    return friendly_label(ContactRole(value))
