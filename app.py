from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
from dotenv import load_dotenv

from document_manager.database.repository import get_customers, get_template, get_template_names, get_customers_values
from document_manager.documents.generation import generate_pdf, generate_rtf
from document_manager.services.document_service import load_table_definitions, load_image_definitions, generate_docx_from_queries
from document_manager.documents.templating import render_template


load_dotenv()


st.set_page_config(
    page_title="Customer Document Manager",
    page_icon="📄",
    layout="wide",
)

st.title("Customer Document Manager")
st.page_link("pages/1_Block_preview.py", label="Preview templates built from blocks")
st.page_link("pages/2_Template_builder.py", label="Build a template from reusable blocks")

template_names = get_template_names()

if not template_names:
    st.error("Active templates were not found. Please add templates to the document_manager.database.repository.")
else:
    template_name = st.selectbox(
        "SELECT TEMPLATE",
        template_names,
    )

selected_customer = st.selectbox(
    label="CLICK TO SELECT CUSTOMER",
    options=get_customers(),
    format_func=lambda customer: (
        f"{customer[0]} - {customer[1]} {customer[2]}"
    ),
)

customer_id = selected_customer[0]

template_row = get_template(template_name)
if template_row is None:
    st.error("Active customer_details template was not found.")
else:
    template_text, template_version, template_format, template_file, template_version_id = template_row

    if template_format == "text":
        available_formats = ["RTF", "PDF"]
    elif template_format == "docx":
        available_formats = ["DOCX"]
    else:
        st.error("Unsupported template format.")
        st.stop()

    document_format = st.radio(
        "SELECT DOCUMENT FORMAT",
        options=available_formats,
        horizontal=True,
    )

    if template_format == "docx":
        values = get_customers_values(customer_id)

        if values is None:
            st.error("Customer details were not found in the document_manager.database.repository.")
            st.stop()

        values["current_date"] = datetime.now(ZoneInfo("Asia/Yerevan")).strftime("%d/%m/%Y")

        st.caption(f"Template version: {template_version}")

        if st.button("Generate DOCX", type="primary"):
            document_context = {
                "entity": {"schema": "public", "table": "customers"},
                "key": {"customer_id": customer_id},
            }
            try:
                table_definitions = load_table_definitions(template_version_id)
                docx_data = generate_docx_from_queries(
                    template_file,
                    values,
                    table_definitions,
                    document_context=document_context,
                    images=load_image_definitions(template_version_id),
                )
            except ValueError as error:
                st.error(str(error))
                st.stop()

            st.download_button(
                label="Download DOCX",
                data=docx_data,
                file_name=f"customer_{customer_id}.docx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
            )
        st.stop()

    current_date = datetime.now(ZoneInfo("Asia/Yerevan")).strftime("%d/%m/%Y")

    values = get_customers_values(customer_id)

    if values is None:
        st.error("Customer details were not found in the document_manager.database.repository.")
        st.stop()

    values["current_date"] = current_date
    try:
        rendered_text = render_template(template_text, values)
    except ValueError as error:
        st.error(str(error))
        st.stop()

    st.subheader("Document Preview")
    st.text(rendered_text)
    st.caption(f"Template version: {template_version}")

    if st.button("Generate document", type="primary"):
        if document_format == "PDF":
            pdf_data = generate_pdf(rendered_text)
            st.download_button(
                label="Download PDF",
                data=pdf_data,
                file_name=f"customer_{customer_id}.pdf",
                mime="application/pdf",
            )
        else:
            rtf_data = generate_rtf(rendered_text)
            st.download_button(
                label="Download RTF",
                data=rtf_data,
                file_name=f"customer_{customer_id}.rtf",
                mime="application/rtf",
            )
