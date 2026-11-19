from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import streamlit as st
from dotenv import load_dotenv

from document_manager.database.repository import (
    get_block_template_versions,
    get_customers,
    get_customers_values,
    get_template_version_blocks,
)
from document_manager.services.document_service import generate_document_from_blocks


load_dotenv(Path(__file__).resolve().parents[1] / ".env")
st.set_page_config(page_title="Block template preview", layout="wide")
st.title("Block template preview")
st.caption("Inspect a template's blocks and generate a document for a selected customer. Drafts can be previewed without publishing.")
st.page_link("pages/2_Template_builder.py", label="Build a template from reusable blocks")

try:
    versions = get_block_template_versions()
    customers = get_customers()
except psycopg.Error:
    st.error("Could not load templates and customers. Check the database connection.")
    st.stop()

if not versions:
    st.info("No draft or published block templates are available.")
    st.stop()
if not customers:
    st.info("No customers are available.")
    st.stop()

requested_version = st.session_state.pop("block_preview_requested_version", None)
versions_by_id = {version["template_version_id"]: version for version in versions}
if requested_version in versions_by_id:
    st.session_state["block_preview_version_id"] = requested_version
elif st.session_state.get("block_preview_version_id") not in versions_by_id:
    st.session_state.pop("block_preview_version_id", None)
version_choice = st.selectbox(
    "Template version", list(versions_by_id), key="block_preview_version_id",
    format_func=lambda key: f"{versions_by_id[key]['name']} - v{versions_by_id[key]['version_number']} ({versions_by_id[key]['status']})",
)
selected = versions_by_id[version_choice]
customer = st.selectbox(
    "Customer", customers,
    format_func=lambda row: f"{row[0]} - {row[1]} {row[2]}",
)
version_id = selected["template_version_id"]
customer_id = customer[0]
document_format = st.radio("Document format", ["DOCX", "RTF", "PDF"], horizontal=True)
selection = (version_id, customer_id, document_format)

st.subheader("Template composition")
st.caption(f"Layout: {selected['layout_name']} - v{selected['layout_version_number']}")
try:
    blocks = get_template_version_blocks(version_id)
except psycopg.Error:
    st.error("Could not load the template's blocks.")
    st.stop()
if blocks:
    st.table([{
        "Area": block["block_type"].title(), "Position": block["position"],
        "Block": block["name"], "Version": block["version_number"],
    } for block in blocks])
else:
    st.warning("This template has no blocks yet.")

previous = st.session_state.get("block_preview_result")
if previous and previous["selection"] != selection:
    del st.session_state["block_preview_result"]

if st.button("Generate preview", type="primary", disabled=not blocks):
    st.session_state.pop("block_preview_result", None)
    try:
        with st.spinner("Assembling and generating the document..."):
            values = get_customers_values(customer_id)
            if values is None:
                raise ValueError("The selected customer was not found.")
            values["current_date"] = datetime.now(ZoneInfo("Asia/Yerevan")).strftime("%d/%m/%Y")
            context = {"entity": {"schema": "public", "table": "customers"},
                       "key": {"customer_id": customer_id}}
            data = generate_document_from_blocks(version_id, values, context, document_format=document_format)
        st.session_state["block_preview_result"] = {
            "selection": selection, "data": data,
            "filename": f"template_{version_id}_customer_{customer_id}.{document_format.lower()}",
        }
    except ValueError as error:
        st.error(str(error))
    except psycopg.Error:
        st.error("Could not assemble the template or read its data. Check the template configuration and database connection.")

result = st.session_state.get("block_preview_result")
if result and result["selection"] == selection:
    st.success("Document generated. Download it to inspect the layout.")
    st.download_button(
        f"Download {document_format}", data=result["data"], file_name=result["filename"],
        mime=("application/pdf" if document_format == "PDF" else "application/rtf" if document_format == "RTF" else
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    )
