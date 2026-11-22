"""Save reusable block compositions as new draft template versions."""

import re
from contextlib import contextmanager
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from document_manager.database.connection import get_connection, load_query
from document_manager.documents.html_document import validate_page_settings
from document_manager.documents.exporters.docx import export_html_to_docx
from document_manager.documents.exporters.pdf import export_html_to_pdf
from document_manager.documents.html_rendering import render_html_template
from document_manager.services.document_service import build_query_tables


def find_placeholder_names(layout, blocks):
    """Discover fields for the editor; the renderer validates them on save."""
    html = "\n".join([layout["content_html"], *(block["content_html"] for block in blocks)])
    return sorted(set(re.findall(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}", html)))


def _positive_id(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer.")


def _validate_composition(layout_version_id, body_block_ids, header_block_id, footer_block_id, tables, images):
    """Validate selections without creating or reserving database identities."""
    _positive_id(layout_version_id, "Layout version ID")
    if not isinstance(body_block_ids, list) or not body_block_ids:
        raise ValueError("Add at least one body block.")
    bindings = []
    for role, ids in (("header", [] if header_block_id is None else [header_block_id]),
                      ("body", body_block_ids),
                      ("footer", [] if footer_block_id is None else [footer_block_id])):
        for position, block_id in enumerate(ids, 1):
            _positive_id(block_id, "Block version ID")
            bindings.append((block_id, role, position))
    tables = {} if tables is None else tables
    images = {} if images is None else images
    for mapping in (tables, images):
        if not isinstance(mapping, dict):
            raise ValueError("Placeholder settings must be dictionaries.")
        for field, setting_id in mapping.items():
            if not isinstance(field, str) or len(field) > 100 or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", field):
                raise ValueError("Placeholder names must be valid field names of at most 100 characters.")
            _positive_id(setting_id, "Placeholder setting ID")
    if tables.keys() & images.keys():
        raise ValueError("A placeholder cannot be both a table and an image.")
    return bindings, tables, images


def _table_definition(setting):
    return {
        **setting["query_config"],
        "columns": [{"field": column["key"], "title": column["title"]}
                    for column in setting["columns_config"]],
        "style": setting["style"],
    }


def _image_definition(item):
    return {"data": bytes(item["image_data"]), "mime_type": item["mime_type"],
            "width_mm": item["width_mm"], "height_mm": item["height_mm"]}


def _validate_assembled(assembled):
    if assembled is None:
        raise ValueError("The assembled composition was not returned by the database.")
    if assembled["style_config"] != {}:
        raise ValueError("Custom style profiles are not supported yet. Choose another layout.")
    validate_page_settings(assembled["page_settings"])


@contextmanager
def _draft_composition(name, layout_version_id, body_block_ids,
                        header_block_id=None, footer_block_id=None,
                        template_id=None, tables=None, images=None):
    """Create a draft for Save draft only; failures roll back its records."""
    bindings, tables, images = _validate_composition(
        layout_version_id, body_block_ids, header_block_id, footer_block_id, tables, images)
    if template_id is None:
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 255:
            raise ValueError("Enter a template name of 1 to 255 characters.")
    else:
        _positive_id(template_id, "Template ID")

    with get_connection() as connection, connection.transaction():
        with connection.cursor(row_factory=dict_row) as cursor:
            if template_id is None:
                cursor.execute(load_query("insert_builder_template.sql"),
                               (f"template_{uuid4().hex}", name.strip()))
                template_id = cursor.fetchone()["template_id"]
            else:
                # Serialize version allocation for this catalog entry.
                cursor.execute(load_query("lock_builder_template.sql"), (template_id,))
                if cursor.fetchone() is None:
                    raise ValueError("The selected template is missing or archived.")
            cursor.execute(load_query("insert_builder_version.sql"),
                           (template_id, layout_version_id, template_id))
            result = cursor.fetchone()
            version_id = result["template_version_id"]
            for block_id, role, position in bindings:
                cursor.execute(load_query("insert_builder_block.sql"), (version_id, block_id, role, position))

            table_definitions = {}
            for field, setting_id in tables.items():
                cursor.execute(load_query("copy_builder_table.sql"), (version_id, field, setting_id))
                setting = cursor.fetchone()
                if setting is None:
                    raise ValueError(f"The selected table settings for '{field}' are unavailable.")
                table_definitions[field] = _table_definition(setting)
            for field, setting_id in images.items():
                cursor.execute(load_query("copy_builder_image.sql"), (version_id, field, setting_id))
                if cursor.fetchone() is None:
                    raise ValueError(f"The selected image settings for '{field}' are unavailable.")
            cursor.execute(load_query("get_template_images.sql"), (version_id,))
            image_definitions = {
                item["placeholder_name"]: _image_definition(item)
                for item in cursor.fetchall()
            }
            # Assemble with the existing SQL procedure in the same transaction.
            cursor.execute(load_query("assemble_template.sql"), (version_id,))
            assembled = cursor.fetchone()
            _validate_assembled(assembled)
            yield result, assembled, table_definitions, image_definitions


def save_block_template_draft(name, layout_version_id, body_block_ids,
                              header_block_id=None, footer_block_id=None,
                              template_id=None, tables=None, images=None):
    """Save and validate a new draft atomically, without changing older versions."""
    with _draft_composition(name, layout_version_id, body_block_ids, header_block_id, footer_block_id,
                            template_id, tables, images) as (result, assembled, definitions, assets):
        empty_tables = {
            field: {"columns": [{"key": column["field"], "title": column["title"]}
                                for column in definition["columns"]],
                    "rows": [], "style": definition["style"]}
            for field, definition in definitions.items()
        }
        rendered = render_html_template(assembled["html_template"], {}, empty_tables, assets)
        # Preflight without fetching business data; failures roll back the save.
        export_html_to_docx(rendered, assembled["page_settings"], assets=assets)
        return result


def preview_block_composition(layout_version_id, body_block_ids, values, document_context=None,
                               header_block_id=None, footer_block_id=None, tables=None, images=None):
    """Generate an unsaved PDF using SELECT-only assembly and setting lookups."""
    if not isinstance(values, dict):
        raise ValueError("Preview values must be a dictionary.")
    bindings, tables, images = _validate_composition(
        layout_version_id, body_block_ids, header_block_id, footer_block_id, tables, images)
    requested_blocks = [{"block_version_id": block_id, "block_type": role, "position": position}
                        for block_id, role, position in bindings]
    definitions, assets = {}, {}
    with get_connection() as connection:
        connection.read_only = True
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(load_query("assemble_composition.sql"), (layout_version_id, Jsonb(requested_blocks)))
            assembled = cursor.fetchone()
            _validate_assembled(assembled)
            for field, setting_id in tables.items():
                cursor.execute(load_query("get_builder_table_setting.sql"), (setting_id,))
                setting = cursor.fetchone()
                if setting is None:
                    raise ValueError(f"The selected table settings for '{field}' are unavailable.")
                definitions[field] = _table_definition(setting)
            for field, setting_id in images.items():
                cursor.execute(load_query("get_builder_image_setting.sql"), (setting_id,))
                setting = cursor.fetchone()
                if setting is None:
                    raise ValueError(f"The selected image settings for '{field}' are unavailable.")
                assets[field] = _image_definition(setting)
    query_tables = build_query_tables(definitions, document_context)
    rendered = render_html_template(assembled["html_template"], values, query_tables, assets)
    return export_html_to_pdf(rendered, assembled["page_settings"], assets=assets)
