"""Inspect PostgreSQL tables and validate declarative table requests.

This module reads schema metadata only. It does not retrieve document data,
construct data queries, or change database objects.
"""

from psycopg.rows import dict_row

from document_manager.database.connection import get_connection, load_query


def _validate_name(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string.")


def _validate_reference(reference, label):
    if not isinstance(reference, dict):
        raise ValueError(f"{label} must specify a schema and a table.")
    _validate_name(reference.get("schema"), f"{label} schema")
    _validate_name(reference.get("table"), f"{label} table")
    return reference["schema"], reference["table"]


def list_tables(schema="public"):
    _validate_name(schema, "Schema")
    with get_connection() as connection:
        connection.read_only = True
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(load_query("get_metadata_tables.sql"), (schema,))
            return [row["table_name"] for row in cursor.fetchall()]


def get_table_metadata(schema, table):
    _validate_name(schema, "Schema")
    _validate_name(table, "Table")
    parameters = (schema, table)
    with get_connection() as connection:
        connection.read_only = True
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(load_query("get_metadata_columns.sql"), parameters)
            columns = cursor.fetchall()
            if not columns:
                raise ValueError(f"Table '{schema}.{table}' is unavailable or has no readable columns.")

            cursor.execute(load_query("get_metadata_primary_key.sql"), parameters)
            primary_key = [row["column_name"] for row in cursor.fetchall()]
            cursor.execute(load_query("get_metadata_foreign_keys.sql"), parameters)
            foreign_keys = cursor.fetchall()

    return {
        "schema": schema,
        "table": table,
        "columns": columns,
        "primary_key": primary_key,
        "foreign_keys": foreign_keys,
    }


def validate_table_request(table_definition, document_context=None):
    if not isinstance(table_definition, dict):
        raise ValueError("Table definition must be a dictionary.")

    scope = table_definition.get("scope", "related")
    if scope not in ("all", "related"):
        raise ValueError("Scope must be 'all' or 'related'.")
    if scope == "all":
        if document_context is not None or "relation" in table_definition:
            raise ValueError("Scope 'all' must not specify a relation or document context.")
    elif not isinstance(document_context, dict):
        raise ValueError("Scope 'related' requires a document context dictionary.")

    source_reference = _validate_reference(table_definition.get("source"), "Source")
    source = get_table_metadata(*source_reference)

    field_names = {column["name"] for column in source["columns"]}
    columns = table_definition.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError("At least one output column is required.")
    for column in columns:
        if not isinstance(column, dict):
            raise ValueError("Each output column must specify a field and a title.")
        field = column.get("field")
        _validate_name(field, "Output field")
        if field not in field_names:
            raise ValueError(f"Output field '{field}' does not exist in the source.")
        _validate_name(column.get("title"), "Column title")

    order_by = table_definition.get("order_by", [])
    if not isinstance(order_by, list):
        raise ValueError("Sort settings must be a list.")
    for ordering in order_by:
        if not isinstance(ordering, dict):
            raise ValueError("Each sort setting must specify a field and a direction.")
        field = ordering.get("field")
        _validate_name(field, "Sort field")
        if field not in field_names:
            raise ValueError(f"Sort field '{field}' does not exist in the source.")
        if ordering.get("direction") not in ("asc", "desc"):
            raise ValueError("Sort direction must be 'asc' or 'desc'.")

    if scope == "all":
        return {"source": source, "context": None, "relation": None}

    context_reference = _validate_reference(document_context.get("entity"), "Context entity")
    context = get_table_metadata(*context_reference)
    key = document_context.get("key")
    if not context["primary_key"]:
        raise ValueError("The context entity must have a primary key.")
    if not isinstance(key, dict) or set(key) != set(context["primary_key"]):
        raise ValueError("Context key must contain exactly the entity's primary-key fields.")
    if any(value is None for value in key.values()):
        raise ValueError("Context primary-key values must not be None.")

    relation_name = table_definition.get("relation")
    _validate_name(relation_name, "Relation")
    relation = next(
        (item for item in source["foreign_keys"] if item["name"] == relation_name),
        None,
    )
    if relation is None:
        raise ValueError(f"Relation '{relation_name}' does not exist on the source table.")
    if (relation["referenced_schema"], relation["referenced_table"]) != context_reference:
        raise ValueError("The selected relation does not reference the context entity.")
    if set(relation["referenced_columns"]) != set(context["primary_key"]):
        raise ValueError("The selected relation must reference the context entity's primary key.")

    return {"source": source, "context": context, "relation": relation}
