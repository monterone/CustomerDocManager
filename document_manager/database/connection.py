"""PostgreSQL connections and packaged SQL resources."""

import os
from pathlib import Path

import psycopg


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
