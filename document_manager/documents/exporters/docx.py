from io import BytesIO
import re

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt

from document_manager.documents.images import prepare_image
from document_manager.documents.html_document import HtmlElement, get_table_rows, iter_inline_tokens, parse_html_document, validate_page_settings


_ALIGNMENTS = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def _write_table(container, element, width, in_body, assets, max_height):
    rows = get_table_rows(element)
    columns = len(rows[0].children)
    options = {} if in_body else {"width": width}
    table = container.add_table(rows=0, cols=columns, **options)
    table.style = "Table Grid"
    table.autofit = False
    column_width = int(width / columns)
    for column in table.columns:
        column.width = column_width
    for index, source_row in enumerate(rows):
        row = table.add_row()
        if index == 0 and all(cell.tag == "th" for cell in source_row.children):
            repeat = OxmlElement("w:tblHeader")
            repeat.set(qn("w:val"), "true")
            row._tr.get_or_add_trPr().append(repeat)
        for cell, source_cell in zip(row.cells, source_row.children):
            cell.width = column_width
            margins = OxmlElement("w:tcMar")
            for side in ("left", "right"):
                margin = OxmlElement(f"w:{side}")
                margin.set(qn("w:w"), str(Mm(2).twips))
                margin.set(qn("w:type"), "dxa")
                margins.append(margin)
            cell._tc.get_or_add_tcPr().append(margins)
            paragraphs = [node for node in source_cell.children if isinstance(node, HtmlElement) and node.tag == "p"]
            for paragraph_index, source in enumerate(paragraphs or [source_cell]):
                paragraph = cell.paragraphs[0] if paragraph_index == 0 else cell.add_paragraph()
                _write_paragraph(paragraph, source, bold=source_cell.tag == "th",
                                 assets=assets, max_width=column_width - Mm(4),
                                 max_height=max_height)


def _write_image(run, attributes, assets, max_width, max_height):
    image = prepare_image(attributes, assets, max_width / 36000, max_height / 36000)
    width, height = round(image.width_mm * 36000), round(image.height_mm * 36000)
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions are too small for DOCX.")
    picture = run.add_picture(BytesIO(image.data), width=width, height=height)
    picture._inline.docPr.set("descr", image.alt)


def _write_paragraph(paragraph, element, bold=False, assets=None,
                     max_width=None, max_height=None):
    paragraph.alignment = _ALIGNMENTS[element.attrs.get("data-align", "left")]
    has_text = False
    pending_space = False
    for kind, text, bold, italic, underline in iter_inline_tokens(element, bold=bold):
        if kind == "img":
            if pending_space and has_text:
                paragraph.add_run(" ")
            _write_image(paragraph.add_run(), text, assets, max_width, max_height)
            has_text, pending_space = True, False
            continue
        if kind == "br":
            paragraph.add_run().add_break()
            has_text = pending_space = False
            continue
        if kind == "span":
            if pending_space and has_text:
                paragraph.add_run(" ")
            field = OxmlElement("w:fldSimple")
            field.set(qn("w:instr"), "PAGE")
            field.set(qn("w:dirty"), "true")
            paragraph._p.append(field)
            has_text, pending_space = True, False
            continue
        text = re.sub(r"[ \t\r\n\f]+", " ", text)
        content = text.strip(" ")
        if not content:
            pending_space = pending_space or bool(text)
            continue
        if has_text and (pending_space or text.startswith(" ")):
            paragraph.add_run(" ")
        run = paragraph.add_run(content)
        run.bold, run.italic, run.underline = bold, italic, underline
        has_text, pending_space = True, text.endswith(" ")


def export_html_to_docx(html, page_settings=None, assets=None):
    regions = parse_html_document(html)
    settings = validate_page_settings(page_settings)
    if assets is None:
        assets = {}
    if not isinstance(assets, dict):
        raise ValueError("Image assets must be a dictionary keyed by internal references.")
    document = Document()
    section = document.sections[0]
    section.orientation = (WD_ORIENT.LANDSCAPE if settings["page_width_mm"] > settings["page_height_mm"]
                           else WD_ORIENT.PORTRAIT)
    for setting, value in settings.items():
        attribute = {
            "margin_top_mm": "top_margin", "margin_bottom_mm": "bottom_margin",
            "margin_left_mm": "left_margin", "margin_right_mm": "right_margin",
        }.get(setting, setting.removesuffix("_mm"))
        setattr(section, attribute, Mm(value))
    for name, size in {"Normal": 11, "Heading 1": 18, "Heading 2": 14,
                       "Heading 3": 12, "Header": 10, "Footer": 10}.items():
        style = document.styles[name]
        style.font.name, style.font.size = "Arial", Pt(size)
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(6)
    for role, region in regions.items():
        container = document if role == "main" else getattr(section, role)
        width = section.page_width - section.left_margin - section.right_margin
        height = section.page_height - section.top_margin - section.bottom_margin
        for index, element in enumerate(region.children):
            if element.tag == "table":
                if role != "main" and index == 0:
                    initial = container.paragraphs[0]._p
                    initial.getparent().remove(initial)
                _write_table(container, element,
                             width, in_body=role == "main", assets=assets, max_height=height)
                if role != "main" and index == len(region.children) - 1:
                    container.add_paragraph()
                continue
            style = (f"Heading {element.tag[1]}" if element.tag.startswith("h")
                     else {"main": "Normal", "header": "Header", "footer": "Footer"}[role])
            paragraph = (container.paragraphs[0] if role != "main" and index == 0
                         else container.add_paragraph())
            paragraph.style = style
            _write_paragraph(paragraph, element, assets=assets,
                             max_width=width, max_height=height)
    output = BytesIO()
    document.save(output)
    return output.getvalue()
