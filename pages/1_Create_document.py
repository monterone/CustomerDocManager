"""Create documents from saved template versions, regardless of storage mode."""

from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
import streamlit as st
from dotenv import load_dotenv

from document_manager.database.repository import get_document_versions, get_customers, get_customers_values, get_template_version_blocks
from document_manager.paths import PROJECT_ROOT
from document_manager.services.document_service import available_document_formats, generate_document_from_version
from document_manager.ui.pdf_preview import show_pdf_preview
from document_manager.ui.labels import template_labels


load_dotenv(PROJECT_ROOT / ".env")
st.title("Create document")
st.caption("Choose a saved template, version, and customer. Generate a PDF to view its pages, or download another supported format.")
st.page_link("pages/2_Template_builder.py", label="Build or update a template")

try:
    all_versions = get_document_versions()
    customers = get_customers()
except psycopg.Error:
    st.session_state.pop("document_result", None)
    st.error("Could not load templates and customers. Check the database connection.")
    st.stop()

requested_version = st.session_state.pop("document_requested_version", None)
if requested_version is None:
    requested_version = st.session_state.pop("block_preview_requested_version", None)
requested = next((version for version in all_versions if version["template_version_id"] == requested_version), None)
if requested and requested["status"] == "draft":
    st.session_state["document_include_drafts"] = True
include_drafts = st.checkbox("Include draft versions", key="document_include_drafts")
versions = [version for version in all_versions if include_drafts or version["status"] == "published"]
if not versions or not customers:
    st.session_state.pop("document_result", None)
    if not versions:
        st.info("No template versions are available. Include drafts or create a template in the builder.")
    if not customers:
        st.info("No customers are available.")
    st.stop()

templates = {version["template_id"]: version for version in versions}
labels = template_labels(templates)
if requested and requested["template_id"] in templates:
    st.session_state["document_template_id"] = requested["template_id"]
elif st.session_state.get("document_template_id") not in templates:
    st.session_state.pop("document_template_id", None)
template_id = st.selectbox("Template", list(templates), key="document_template_id",
                           format_func=labels.__getitem__)
version_options = {version["template_version_id"]: version for version in versions if version["template_id"] == template_id}
version_labels = {key: f"v{version['version_number']} ({version['status']})"
                  for key, version in version_options.items()}
# A different template or status needs a new widget, not the previous label state.
version_widget_key = f"document_version_choice_{template_id}_{tuple(version_labels.items())}"
if requested and requested_version in version_options:
    st.session_state["document_version_id"] = requested_version
elif st.session_state.get("document_version_id") not in version_options:
    st.session_state["document_version_id"] = next(iter(version_options))
if requested or st.session_state.get(version_widget_key) not in version_options:
    st.session_state[version_widget_key] = st.session_state["document_version_id"]
version_id = st.selectbox("Version", list(version_options), key=version_widget_key,
                          format_func=version_labels.__getitem__)
st.session_state["document_version_id"] = version_id
selected = version_options[version_id]
if selected["status"] == "draft":
    st.caption("Draft version: generation is available for checking before publication.")

customers_by_id = {row[0]: row for row in customers}
if st.session_state.get("document_customer_id") not in customers_by_id:
    st.session_state.pop("document_customer_id", None)
customer_id = st.selectbox("Customer", list(customers_by_id), key="document_customer_id",
                           format_func=lambda key: f"{customers_by_id[key][1]} {customers_by_id[key][2]} (#{key})")
try:
    formats = available_document_formats(selected)
except ValueError as error:
    st.session_state.pop("document_result", None)
    st.error(str(error))
    st.stop()
if st.session_state.get("document_format") not in formats:
    st.session_state.pop("document_format", None)
document_format = st.radio("Document format", formats, horizontal=True, key="document_format")
if formats == ["DOCX"]:
    st.caption("This Word template currently supports DOCX output. Download it to inspect the document.")

has_blocks = True
if selected["storage_mode"] == "blocks":
    try:
        blocks = get_template_version_blocks(version_id)
    except psycopg.Error:
        st.session_state.pop("document_result", None)
        st.error("Could not load the template composition. Check the database connection.")
        st.stop()
    has_blocks = bool(blocks)
    with st.expander("Template composition"):
        st.caption(f"Layout: {selected['layout_name']} - v{selected['layout_version_number']}")
        if blocks:
            st.table([{"Area": block["block_type"].title(), "Position": block["position"],
                       "Block": block["name"], "Version": block["version_number"]} for block in blocks])
        else:
            st.warning("This template has no blocks yet. Update it in the builder.")

current_date = datetime.now(ZoneInfo("Asia/Yerevan")).strftime("%d/%m/%Y")
selection = (version_id, customer_id, document_format, current_date)
previous = st.session_state.get("document_result")
if previous and (previous["selection"] != selection or not has_blocks):
    st.session_state.pop("document_result", None)

if st.button("Generate document", type="primary", disabled=not has_blocks):
    st.session_state.pop("document_result", None)
    try:
        with st.spinner("Generating the document..."):
            values = get_customers_values(customer_id)
            if values is None:
                raise ValueError("The selected customer was not found.")
            values = {**values, "current_date": current_date}
            context = {"entity": {"schema": "public", "table": "customers"}, "key": {"customer_id": customer_id}}
            data = generate_document_from_version(version_id, values, context, document_format=document_format)
        st.session_state["document_result"] = {
            "selection": selection, "data": data,
            "filename": f"template_{version_id}_customer_{customer_id}.{document_format.lower()}",
        }
    except ValueError as error:
        st.error(str(error))
    except psycopg.Error:
        st.error("Could not generate the document. Check the template settings and database connection.")

result = st.session_state.get("document_result")
if result and result["selection"] == selection:
    st.success("Document generated.")
    if document_format == "PDF":
        show_pdf_preview(result["data"], key_prefix="document_pdf_")
    mime_types = {"PDF": "application/pdf", "RTF": "application/rtf",
                  "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    st.download_button(f"Download {document_format}", data=result["data"], file_name=result["filename"],
                       mime=mime_types[document_format])
