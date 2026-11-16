from database import get_template_tables
from document_generation import generate_docx
from table_query import fetch_table_rows


def load_table_definitions(template_version_id):
    definitions = {}
    for setting in get_template_tables(template_version_id):
        name = setting["placeholder_name"]
        query_config = setting["query_config"]
        if not isinstance(query_config, dict):
            raise ValueError(f"Query configuration is missing for table '{name}'.")

        definitions[name] = {
            **query_config,
            "columns": [
                {"field": column["key"], "title": column["title"]}
                for column in setting["columns_config"]
            ],
            "style": setting["style"],
        }
    return definitions


def build_query_tables(table_definitions, document_context=None):
    if not isinstance(table_definitions, dict):
        raise ValueError("Table definitions must be a dictionary keyed by placeholder names.")

    tables = {}
    for name, definition in table_definitions.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Each table placeholder must have a non-empty name.")
        if not isinstance(definition, dict):
            raise ValueError(f"Table definition '{name}' must be a dictionary.")

        context = None if definition.get("scope") == "all" else document_context
        rows = fetch_table_rows(definition, context)
        tables[name] = {
            "columns": [
                {"key": column["field"], "title": column["title"]}
                for column in definition["columns"]
            ],
            "rows": rows,
            "style": definition.get("style", "Table Grid"),
        }

    return tables


def generate_docx_from_queries(template_file, values, table_definitions, document_context=None):
    if not template_file:
        raise ValueError("The DOCX template file is empty.")
    tables = build_query_tables(table_definitions, document_context)
    return generate_docx(template_file, values, tables=tables)
