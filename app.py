import json
import os
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st
from dotenv import load_dotenv

from database import get_customers, get_template, get_template_names, get_customers_values
from document_generation import generate_pdf, generate_rtf
from document_service import load_table_definitions, generate_docx_from_queries
from templating import render_template


load_dotenv()


st.set_page_config(
    page_title="Customer Document Manager",
    page_icon="📄",
    layout="wide",
)

st.title("Customer Document Manager")

template_names = get_template_names()

if not template_names:
    st.error("Active templates were not found. Please add templates to the database.")
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

recipient_email = st.text_input("Recipient email")
send_by_email = st.button("Send document by email")

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
            st.error("Customer details were not found in the database.")
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
        st.error("Customer details were not found in the database.")
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

    if send_by_email:
        if not recipient_email.strip():
            st.error("Enter a recipient email address.")
        else:
            webhook_url = os.getenv("N8N_WEBHOOK_URL")
            if not webhook_url:
                st.error("N8N_WEBHOOK_URL is not configured.")
            else:
                payload = json.dumps(
                    {
                        "customer_id": customer_id,
                        "email": recipient_email.strip(),
                        "document_format": document_format,
                        "template_name": template_name
                    }
                ).encode("utf-8")
                request = Request(
                    webhook_url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                try:
                    with urlopen(request, timeout=30) as response:
                        response.read()
                except HTTPError as error:
                    st.error(f"n8n returned HTTP {error.code}.")
                except (URLError, TimeoutError) as error:
                    st.error(f"Could not connect to n8n: {error}")
                else:
                    st.success("Request sent to n8n.")
