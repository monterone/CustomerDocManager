"""Create independent page layouts without changing existing versions."""

from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from document_manager.database.connection import get_connection, load_query
from document_manager.documents.html_document import validate_page_settings


LAYOUT_HTML = '''<!DOCTYPE html>
<html>
  <head><meta charset="utf-8"></head>
  <body>
    <!-- slot:header -->
    <!-- slot:body -->
    <!-- slot:footer -->
  </body>
</html>
'''


def create_layout(name, page_settings):
    """Validate geometry, then save a new layout and return its identity."""
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 255:
        raise ValueError("Layout name must contain between 1 and 255 characters.")
    settings = validate_page_settings(page_settings)
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(load_query("insert_layout.sql"),
                           (f"layout_{uuid4().hex}", name.strip(), LAYOUT_HTML, Jsonb(settings)))
            return cursor.fetchone()
