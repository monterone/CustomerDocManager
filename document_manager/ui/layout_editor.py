"""Page layout creation controls shared by the template builder."""

import psycopg
import streamlit as st

from document_manager.documents.html_document import DEFAULT_PAGE_SETTINGS
from document_manager.services.layout_service import create_layout


def show_layout_creator():
    with st.expander("Create layout"):
        st.caption("Create a reusable page layout with header, body, and footer areas. All measurements are in millimeters.")
        with st.form("create_layout"):
            name = st.text_input("Layout name", max_chars=255)
            paper = st.selectbox("Page size", ["A4", "A5", "Letter"])
            orientation = st.radio("Orientation", ["Portrait", "Landscape"], horizontal=True)
            settings = {}
            left, right = st.columns(2)
            for index, (key, default) in enumerate(DEFAULT_PAGE_SETTINGS.items()):
                if key.startswith("page_"):
                    continue
                column = left if index % 2 == 0 else right
                settings[key] = column.number_input(
                    key.removesuffix("_mm").replace("_", " ").capitalize() + " (mm)",
                    min_value=0.0, value=float(default), step=1.0, key=f"layout_{key}")
            st.caption("Header and footer content must fit within the reserved top and bottom margins.")
            submitted = st.form_submit_button("Save layout")
        if submitted:
            width, height = {"A4": (210, 297), "A5": (148, 210), "Letter": (215.9, 279.4)}[paper]
            if orientation == "Landscape":
                width, height = height, width
            settings.update(page_width_mm=width, page_height_mm=height)
            try:
                layout = create_layout(name, settings)
            except ValueError as error:
                st.error(str(error))
            except psycopg.Error:
                st.error("Could not save the layout. Check the database connection and try again.")
            else:
                st.session_state["builder_requested_layout"] = layout["layout_version_id"]
                st.session_state["builder_layout_message"] = f"Layout '{layout['name']}' created."
                st.rerun()
