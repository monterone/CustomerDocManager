import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import streamlit as st
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


load_dotenv()


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def get_customers():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT customer_id, first_name, surname
                FROM public.customers
                ORDER BY customer_id
                """
            )
            return cursor.fetchall()


def get_template():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT template_text, version
                FROM public.document_templates
                WHERE name = %s AND is_active = TRUE
                ORDER BY version DESC
                LIMIT 1
                """,
                ("customer_details",),
            )
            return cursor.fetchone()


def generate_pdf(rendered_text):
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)

    font_path = Path(__file__).parent / "assets" / "fonts" / "NotoSansArmenian-Regular.ttf"
    font_bold_path = Path(__file__).parent / "assets" / "fonts" / "NotoSansArmenian-Bold.ttf"

    pdfmetrics.registerFont(TTFont("NotoSansArmenian", str(font_path)))
    pdfmetrics.registerFont(TTFont("NotoSansArmenian-Bold", str(font_bold_path)))

    lines = rendered_text.splitlines()
    page_width, page_height = A4
    y_position = page_height - 72

    pdf.setFont("NotoSansArmenian-Bold", 16)
    pdf.drawString(72, y_position, lines[0])
    y_position -= 36

    pdf.setFont("NotoSansArmenian", 12)
    for line in lines[1:]:
        if line:
            pdf.drawString(72, y_position, line)
        y_position -= 24

    pdf.save()
    output.seek(0)
    return output.getvalue()


st.set_page_config(
    page_title="Customer Document Manager",
    page_icon="📄",
    layout="wide",
)

st.title("Customer Document Manager")

selected_customer = st.selectbox(
    label="CLICK TO SELECT CUSTOMER",
    options=get_customers(),
    format_func=lambda customer: (
        f"{customer[0]} - {customer[1]} {customer[2]}"
    ),
)

customer_id = selected_customer[0]
first_name = selected_customer[1]
surname = selected_customer[2]

document_format = st.radio(
    "SELECT DOCUMENT FORMAT",
    ["RTF", "PDF"],
    horizontal=True,
)

template_row = get_template()

if template_row is None:
    st.error("Active customer_details template was not found.")
else:
    template_text, template_version = template_row
    current_date = datetime.now(ZoneInfo("Asia/Yerevan")).strftime("%d/%m/%Y")

    rendered_text = (
        template_text.replace("{{first_name}}", first_name).replace("{{surname}}", surname).replace("{{current_date}}", current_date)
    )

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