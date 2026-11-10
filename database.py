"""PostgreSQL connections and document/customer queries."""

import os

import psycopg
from psycopg.rows import dict_row


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


def get_customers_values(customer_id):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT * FROM public.customers WHERE customer_id = %s",
                (customer_id,),
            )
            return cursor.fetchone()


def get_template(template_name):
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
                (template_name, ),
            )
            return cursor.fetchone()


def get_template_names():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT name
                FROM public.document_templates
                WHERE is_active = TRUE
                ORDER BY name
                """
            )
            return [row[0] for row in cursor.fetchall()]
