import os
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
import streamlit as st
from dotenv import load_dotenv


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
