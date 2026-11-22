from document_manager.database.repository import get_template_tables, get_template_images, get_assembled_template, get_document_version
from document_manager.documents.generation import generate_docx, generate_pdf, generate_rtf
from document_manager.documents.templating import render_template
from document_manager.documents.exporters.docx import export_html_to_docx
from document_manager.documents.exporters.rtf import export_html_to_rtf
from document_manager.documents.exporters.pdf import export_html_to_pdf
from document_manager.documents.html_rendering import render_html_template
from document_manager.database.table_query import fetch_table_rows


def load_image_definitions(template_version_id):
    return {
        setting["placeholder_name"]: {
            "data": bytes(setting["image_data"]),
            "mime_type": setting["mime_type"],
            "width_mm": setting["width_mm"],
            "height_mm": setting["height_mm"],
        }
        for setting in get_template_images(template_version_id)
    }


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


def generate_docx_from_queries(template_file, values, table_definitions, document_context=None, images=None):
    if not template_file:
        raise ValueError("The DOCX template file is empty.")
    tables = build_query_tables(table_definitions, document_context)
    if images is None:
        return generate_docx(template_file, values, tables=tables)
    return generate_docx(template_file, values, tables=tables, images=images)


def generate_document_from_blocks(template_version_id, values, document_context=None, document_format="DOCX"):
    """Use one assembly/data pipeline and select the requested document exporter."""
    exporters = {"DOCX": export_html_to_docx, "RTF": export_html_to_rtf, "PDF": export_html_to_pdf}
    if not isinstance(document_format, str) or document_format not in exporters:
        raise ValueError("Block document format must be DOCX, RTF, or PDF.")
    assembled = get_assembled_template(template_version_id)
    if assembled is None:
        raise ValueError("The assembled template was not returned by the database.")
    if assembled["style_config"] != {}:
        raise ValueError("Custom style profiles are not supported by the HTML exporter yet.")
    definitions = load_table_definitions(template_version_id)
    tables = build_query_tables(definitions, document_context)
    images = load_image_definitions(template_version_id)
    rendered_html = render_html_template(assembled["html_template"], values,
                                         tables=tables, images=images)
    return exporters[document_format](rendered_html, assembled["page_settings"], assets=images)


def generate_docx_from_blocks(template_version_id, values, document_context=None):
    return generate_document_from_blocks(template_version_id, values, document_context, document_format="DOCX")


def available_document_formats(version):
    """Expose formats supported by the existing generation path for this version."""
    if version["storage_mode"] == "blocks":
        return ["PDF", "DOCX", "RTF"]
    if version["storage_mode"] == "file":
        if version["template_format"] == "text":
            return ["PDF", "RTF"]
        if version["template_format"] == "docx":
            return ["DOCX"]
    raise ValueError("This template's storage or content format is not supported.")


def generate_document_from_version(template_version_id, values, document_context=None, document_format="PDF"):
    """Route any selectable saved version to its existing document generator."""
    version = get_document_version(template_version_id)
    if version is None:
        raise ValueError("The selected template version is no longer available. Refresh the page.")
    if document_format not in available_document_formats(version):
        raise ValueError("The selected output format is not supported by this template version.")
    if version["storage_mode"] == "blocks":
        return generate_document_from_blocks(template_version_id, values, document_context, document_format)
    if version["template_format"] == "docx":
        return generate_docx_from_queries(version["template_file"], values,
                                           load_table_definitions(template_version_id), document_context,
                                           images=load_image_definitions(template_version_id))
    rendered = render_template(version["template_text"], values)
    return {"PDF": generate_pdf, "RTF": generate_rtf}[document_format](rendered)
