"""Compose existing reusable blocks without writing HTML or SQL."""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4

import psycopg
import streamlit as st
from dotenv import load_dotenv

from document_manager.database.repository import get_builder_catalog, get_customers, get_customers_values
from document_manager.services.template_builder import (
    find_placeholder_names, save_block_template_draft, preview_block_composition,
)
from document_manager.ui.pdf_preview import show_pdf_preview
from document_manager.ui.labels import template_labels
from document_manager.ui.layout_editor import show_layout_creator


load_dotenv(Path(__file__).resolve().parents[1] / ".env")
st.set_page_config(page_title="Template builder", layout="wide")
st.title("Template builder")
st.caption("Arrange your document on the left and inspect its pages on the right. Save a draft when the composition is ready.")

try:
    catalog = get_builder_catalog()
    customers = get_customers()
except psycopg.Error:
    st.error("Could not load the catalog and customers. Check the database connection.")
    st.stop()

show_layout_creator()
if message := st.session_state.pop("builder_layout_message", None):
    st.success(message)

if not catalog["layouts"] or not any(block["block_type"] == "body" for block in catalog["blocks"]):
    st.info("Add at least one layout and one body block to the catalog before assembling templates.")
    st.stop()

layouts = {item["layout_version_id"]: item for item in catalog["layouts"]}
blocks = {item["block_version_id"]: item for item in catalog["blocks"]}
templates = {item["template_id"]: item for item in catalog["templates"]}
labels = template_labels(templates)

editor, document_preview = st.columns([1, 1.3], gap="large")

with editor.container(height=1100, border=True):
    mode = st.radio("Save as", ["New template", "New version of an existing template"], horizontal=True)
    template_id = None
    name = ""
    if mode == "New template":
        name = st.text_input("Template name", max_chars=255)
    elif templates:
        template_id = st.selectbox("Template", list(templates),
                                   format_func=labels.__getitem__)
        st.caption("Saving adds a draft version. It does not replace or publish any existing version.")
    else:
        st.info("There are no existing templates. Choose New template instead.")
        st.stop()

    requested_layout = st.session_state.pop("builder_requested_layout", None)
    if requested_layout in layouts:
        st.session_state["builder_layout_id"] = requested_layout
    if st.session_state.get("builder_layout_id") not in layouts:
        st.session_state["builder_layout_id"] = next(iter(layouts))
    layout_id = st.selectbox("Layout", list(layouts), key="builder_layout_id",
                             format_func=lambda key: f"{layouts[key]['name']} — v{layouts[key]['version_number']}")
    layout = layouts[layout_id]
    with st.expander("Page settings"):
        st.write({key.replace("_", " "): value for key, value in layout["page_settings"].items()})


    def block_label(key):
        if key is None:
            return "None"
        block = blocks[key]
        return f"{block['name']} — v{block['version_number']} ({block['code']})"


    header_id = st.selectbox("Header", [None] + [key for key, item in blocks.items() if item["block_type"] == "header"],
                             format_func=block_label)
    st.subheader("Body blocks")
    st.caption("Add blocks in document order. You can use a block more than once.")
    if "builder_body" not in st.session_state:
        st.session_state["builder_body"] = []


    def add_body():
        st.session_state["builder_body"].append({"row_id": uuid4().hex, "block_id": st.session_state["builder_body_choice"]})


    def move_body(index, direction):
        rows = st.session_state["builder_body"]
        other = index + direction
        if 0 <= index < len(rows) and 0 <= other < len(rows):
            rows[index], rows[other] = rows[other], rows[index]


    def remove_body(index):
        st.session_state["builder_body"].pop(index)


    st.selectbox("Block to add", [key for key, item in blocks.items() if item["block_type"] == "body"],
                 format_func=block_label, key="builder_body_choice")
    st.button("Add body block", on_click=add_body)
    body_ids = []
    for index, row in enumerate(st.session_state["builder_body"]):
        columns = st.columns([4, 1, 1, 1.6])
        block_id = row["block_id"]
        body_ids.append(block_id)
        columns[0].write(f"{index + 1}. {block_label(block_id) if block_id in blocks else 'Unavailable block'}")
        columns[1].button("Up", key=f"up_{row['row_id']}", disabled=index == 0,
                           on_click=move_body, args=(index, -1))
        columns[2].button("Down", key=f"down_{row['row_id']}", disabled=index == len(st.session_state["builder_body"]) - 1,
                           on_click=move_body, args=(index, 1))
        columns[3].button("Remove", key=f"remove_{row['row_id']}", on_click=remove_body, args=(index,))
    if not body_ids:
        st.info("Add at least one body block.")

    footer_id = st.selectbox("Footer", [None] + [key for key, item in blocks.items() if item["block_type"] == "footer"],
                             format_func=block_label)
    selected_ids = ([header_id] if header_id else []) + body_ids + ([footer_id] if footer_id else [])
    missing_blocks = any(key not in blocks for key in selected_ids)
    selected_blocks = [blocks[key] for key in selected_ids if key in blocks]
    fields = find_placeholder_names(layout, selected_blocks)

    st.subheader("Placeholder content")
    st.caption("Choose the content type for each field. A choice applies to every occurrence of that name in the document. "
               "Text and numbers come from generation data; missing values become None. "
               "Tables and images reuse existing settings, copied into the new version.")
    table_options = {item["table_id"]: item for item in catalog["table_options"]}
    image_options = {item["image_binding_id"]: item for item in catalog["image_options"]}
    table_bindings, image_bindings = {}, {}
    unresolved = []
    field_types = {}
    for field in fields:
        matching_tables = [key for key, item in table_options.items() if item["placeholder_name"] == field]
        matching_images = [key for key, item in image_options.items() if item["placeholder_name"] == field]
        kinds = ["Text or number", "Table", "Image"]
        default_kind = "Table" if matching_tables and not matching_images else "Image" if matching_images and not matching_tables else "Text or number"
        if matching_tables and matching_images:
            kinds.insert(0, "Choose content type")
            default_kind = "Choose content type"
        with st.expander(field, expanded=bool(matching_tables or matching_images)):
            kind = st.selectbox("Content type", kinds, index=kinds.index(default_kind), key=f"builder_kind_{field}")
            field_types[field] = kind
            if kind == "Choose content type":
                unresolved.append(field)
            elif kind == "Table":
                def table_label(key):
                    if key is None:
                        return "Choose table settings"
                    item = table_options[key]
                    titles = ", ".join(column["title"] for column in item["columns_config"])
                    return f"{item['placeholder_name']} — {item['template_name']} v{item['version_number']} — {titles} [#{key}]"
                options = [None] + list(table_options)
                setting = st.selectbox("Table settings", options,
                                       index=options.index(matching_tables[0]) if len(matching_tables) == 1 else 0,
                                       format_func=table_label, key=f"builder_table_{field}")
                if setting is None:
                    unresolved.append(field)
                else:
                    table_bindings[field] = setting
            elif kind == "Image":
                def image_label(key):
                    if key is None:
                        return "Choose image settings"
                    item = image_options[key]
                    return f"{item['image_name']} — {item['template_name']} v{item['version_number']} [#{key}]"
                options = [None] + list(image_options)
                setting = st.selectbox("Image settings", options,
                                       index=options.index(matching_images[0]) if len(matching_images) == 1 else 0,
                                       format_func=image_label, key=f"builder_image_{field}")
                if setting is None:
                    unresolved.append(field)
                else:
                    image_bindings[field] = setting

    st.subheader("Composition summary")
    if selected_blocks:
        positions = {"header": 0, "body": 0, "footer": 0}
        summary = []
        for block in selected_blocks:
            role = block["block_type"]
            positions[role] += 1
            summary.append({"Area": role.title(), "Position": positions[role], "Block": block["name"], "Version": block["version_number"]})
        st.table(summary)
    if unresolved:
        st.warning("Choose content settings for: " + ", ".join(unresolved))
    if missing_blocks:
        st.warning("Remove unavailable blocks before saving.")

    signature = (name.strip(), template_id, layout_id, tuple(selected_ids), tuple(sorted(table_bindings.items())),
                 tuple(sorted(image_bindings.items())), tuple(sorted(field_types.items())))
    saved = st.session_state.get("builder_saved")
    already_saved = bool(saved and saved["signature"] == signature)
    disabled = not body_ids or missing_blocks or bool(unresolved) or (template_id is None and not name.strip()) or already_saved
    if st.button("Save draft", type="primary", disabled=disabled):
        try:
            result = save_block_template_draft(name, layout_id, body_ids, header_id, footer_id,
                                               template_id=template_id, tables=table_bindings, images=image_bindings)
        except ValueError as error:
            st.error(str(error))
        except psycopg.Error:
            st.error("Could not save the draft. Nothing was saved. Check the selected layout, blocks, settings, and database connection.")
        else:
            st.session_state["builder_saved"] = {"signature": signature, "result": result}
            # Preview reads this ID once and selects the newly saved draft.
            st.session_state["document_requested_version"] = result["template_version_id"]
            st.rerun()

    saved = st.session_state.get("builder_saved")
    if saved and saved["signature"] == signature:
        result = saved["result"]
        st.success(f"Draft v{result['version_number']} saved.")
        st.session_state["document_requested_version"] = result["template_version_id"]
        st.page_link("pages/1_Create_document.py", label="Open saved draft")


with document_preview:
    st.subheader("Document preview")
    st.caption("Preview the current composition with real customer data. Saving a draft is a separate action.")
    customer = None
    if customers:
        customer = st.selectbox("Preview customer", customers,
                                format_func=lambda row: f"{row[1]} {row[2]}", key="builder_preview_customer")
    else:
        st.info("Add a customer to generate a document preview.")
    current_date = datetime.now(ZoneInfo("Asia/Yerevan")).strftime("%d/%m/%Y")
    preview_signature = (layout_id, tuple(selected_ids), tuple(sorted(table_bindings.items())),
                         tuple(sorted(image_bindings.items())), tuple(sorted(field_types.items())),
                         customer[0] if customer else None, current_date)
    previous_preview = st.session_state.get("builder_preview")
    changed = previous_preview is not None and previous_preview["signature"] != preview_signature
    if changed:
        del st.session_state["builder_preview"]
        st.info("The composition or customer changed. Update the preview to see the current document.")
    can_preview = bool(body_ids) and not missing_blocks and not unresolved and customer is not None
    if st.button("Update preview", type="primary", disabled=not can_preview):
        st.session_state.pop("builder_preview", None)
        try:
            with st.spinner("Building the document preview..."):
                values = get_customers_values(customer[0])
                if values is None:
                    raise ValueError("The selected customer was not found.")
                values = {**values, "current_date": current_date}
                context = {"entity": {"schema": "public", "table": "customers"},
                           "key": {"customer_id": customer[0]}}
                data = preview_block_composition(layout_id, body_ids, values, context,
                                                  header_block_id=header_id, footer_block_id=footer_id,
                                                  tables=table_bindings, images=image_bindings)
            st.session_state["builder_preview"] = {"signature": preview_signature, "data": data}
        except ValueError as error:
            st.error(str(error))
        except psycopg.Error:
            st.error("Could not build the preview. Check the selected blocks, data settings, and database connection.")
    preview_result = st.session_state.get("builder_preview")
    if preview_result and preview_result["signature"] == preview_signature:
        data = preview_result["data"]
        show_pdf_preview(data, key_prefix="builder_pdf_")
        st.download_button("Download PDF preview", data=data, file_name="document_preview.pdf", mime="application/pdf")
    elif not changed:
        st.info("Choose your blocks and content settings, then click Update preview to see the document here.")
