from psycopg.rows import dict_row

from document_manager.database.connection import get_connection, load_query


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


def get_assembled_template(template_version_id):
    with get_connection() as connection:
        connection.read_only = True
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(load_query("assemble_template.sql"), (template_version_id,))
            return cursor.fetchone()


def get_block_template_versions():
    with get_connection() as connection:
        connection.read_only = True
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(load_query("get_block_template_versions.sql"))
            return cursor.fetchall()


def get_builder_catalog():
    with get_connection() as connection:
        connection.read_only = True
        with connection.cursor(row_factory=dict_row) as cursor:
            catalog = {}
            for name in ("layouts", "blocks", "templates", "table_options", "image_options"):
                cursor.execute(load_query(f"get_builder_{name}.sql"))
                catalog[name] = cursor.fetchall()
            return catalog


def get_template_version_blocks(template_version_id):
    with get_connection() as connection:
        connection.read_only = True
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(load_query("get_template_version_blocks.sql"), (template_version_id,))
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
