"""PostgreSQL connections and document/customer queries."""

import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


queries_dir = Path(__file__).resolve().parent / "queries"


def load_query(filename):
    return (queries_dir / filename).read_text(encoding="utf-8")


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
            cursor.execute(load_query("get_customers.sql"))
            return cursor.fetchall()


def get_customers_values(customer_id):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                load_query("get_customers_values.sql"),
                (customer_id,),
            )
            return cursor.fetchone()


def get_template_tables(template_version_id):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                load_query("get_template_tables.sql"),
                (template_version_id,),
            )
            return cursor.fetchall()


def get_template_images(template_version_id):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(load_query("get_template_images.sql"), (template_version_id,))
            return cursor.fetchall()


def get_template(template_name):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                load_query("get_template.sql"),
                (template_name, ),
            )
            return cursor.fetchone()


def get_template_names():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(load_query("get_template_names.sql"))
            return [row[0] for row in cursor.fetchall()]
