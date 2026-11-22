"""Streamlit entry point and navigation for document creation and template design."""

import streamlit as st


st.set_page_config(page_title="Customer Document Manager", layout="wide")
page = st.navigation([
    st.Page("pages/1_Create_document.py", title="Create document", default=True),
    st.Page("pages/2_Template_builder.py", title="Template builder"),
])
page.run()
