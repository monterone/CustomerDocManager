"""Export the supported HTML document subset directly to PDF."""

from html import escape
from io import BytesIO
from pathlib import Path

import reportlab
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, LongTable, PageTemplate, Paragraph, Spacer
from reportlab.platypus.doctemplate import LayoutError
from reportlab.platypus.paraparser import ParaParser

from document_manager.documents.images import prepare_image
from document_manager.paths import ASSETS_DIR
from document_manager.documents.html_document import HtmlElement, get_table_rows, iter_inline_tokens, parse_html_document, validate_page_settings


def _fonts():
    root = ASSETS_DIR / "fonts"
    fallback = Path(reportlab.__file__).parent / "fonts"
    for name, path in {
        "HtmlPDF": root / "NotoSansArmenian-Regular.ttf",
        "HtmlPDFBold": root / "NotoSansArmenian-Bold.ttf",
        "HtmlPDFFallback": fallback / "Vera.ttf",
        "HtmlPDFFallbackBold": fallback / "VeraBd.ttf",
        "HtmlPDFItalic": fallback / "VeraIt.ttf",
        "HtmlPDFBoldItalic": fallback / "VeraBI.ttf",
    }.items():
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(path)))
        pdfmetrics.registerFontFamily(name, normal=name, bold=name, italic=name, boldItalic=name)


def _text(text, bold, italic=False):
    result = []
    for character in text:
        if character.isspace():
            character = " "
        candidates = ("HtmlPDFBold", "HtmlPDFFallbackBold") if bold else ("HtmlPDF", "HtmlPDFFallback")
        if italic:
            candidates = ("HtmlPDFBoldItalic" if bold else "HtmlPDFItalic",)
        font = next((name for name in candidates if ord(character) in pdfmetrics.getFont(name).face.charToGlyph), None)
        if font is None:
            raise ValueError(f"PDF fonts do not support character U+{ord(character):04X}.")
        result.append(f'<font name="{font}">{escape(character)}</font>')
    return "".join(result)


def export_html_to_pdf(html, page_settings=None, assets=None):
    """Return PDF bytes; reject unsupported HTML and overflowing page regions."""
    regions = parse_html_document(html)
    settings = validate_page_settings(page_settings)
    if assets is None:
        assets = {}
    if not isinstance(assets, dict):
        raise ValueError("Image assets must be a dictionary.")
    _fonts()
    width = settings["page_width_mm"] * mm
    height = settings["page_height_mm"] * mm
    left = settings["margin_left_mm"] * mm
    body_width = width - left - settings["margin_right_mm"] * mm
    body_height = height - (settings["margin_top_mm"] + settings["margin_bottom_mm"]) * mm
    image_sources = {}

    class AssetParser(ParaParser):
        def end_img(self):
            self._stack[-1].src = BytesIO(image_sources[self._stack[-1].src])
            super().end_img()

    def paragraph(element, available_width, available_height, page, small=False, bold=False):
        markup = []
        has_image = False
        for kind, value, token_bold, italic, underline in iter_inline_tokens(element, bold=bold):
            if kind == "img":
                has_image = True
                image = prepare_image(value, assets, available_width / mm, available_height / mm)
                key = f"asset_{len(image_sources)}"
                image_sources[key] = image.data
                markup.append(f'<img src="{key}" width="{image.width_mm * mm}" height="{image.height_mm * mm}" valign="top"/>')
                continue
            if kind == "br":
                markup.append("<br/>")
                continue
            text = str(page) if kind == "span" else value
            part = _text(text, token_bold or element.tag in {"h1", "h2", "h3"}, italic)
            if underline:
                part = f'<u>{part}</u>'
            markup.append(part)
        size = {"h1": 18, "h2": 14, "h3": 12}.get(element.tag, 10 if small else 11)
        # Inline images need their full line height; fixed text leading clips them.
        style = ParagraphStyle("HTML", fontName="HtmlPDF", fontSize=size, leading=size * 1.3,
                               autoLeading="max" if has_image else "off",
                               spaceAfter=6, alignment={"left": 0, "center": 1, "right": 2, "justify": 4}[element.attrs.get("data-align", "left")])
        parsed_style, fragments, _ = AssetParser().parse("".join(markup) or "&#160;", style)
        return Paragraph("", parsed_style, frags=fragments)

    def flowables(region, available_height, page=1, small=False):
        result = []
        if region is None:
            return result
        for element in region.children:
            if element.tag != "table":
                result.append(paragraph(element, body_width, available_height, page, small))
                continue
            rows = get_table_rows(element)
            cell_width = body_width / len(rows[0].children)
            data = []
            for row in rows:
                cells = []
                for cell in row.children:
                    paragraphs = [child for child in cell.children if isinstance(child, HtmlElement) and child.tag == "p"]
                    cells.append([paragraph(node, cell_width - 4 * mm, available_height, page, small, cell.tag == "th") for node in paragraphs or [cell]])
                data.append(cells)
            table = LongTable(data, colWidths=[cell_width] * len(rows[0].children),
                              repeatRows=int(all(cell.tag == "th" for cell in rows[0].children)),
                              splitInRow=1, spaceAfter=6)
            table.setStyle([("GRID", (0, 0), (-1, -1), .5, colors.black),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm)])
            result.append(table)
        return result

    def on_page(canvas, document):
        canvas.saveState()
        try:
            for role, margin, distance in (("header", "top", "header"), ("footer", "bottom", "footer")):
                available = (settings[f"margin_{margin}_mm"] - settings[f"{distance}_distance_mm"]) * mm
                items = flowables(regions.get(role), available, canvas.getPageNumber(), True)
                sizes = [item.wrap(body_width, available)[1] for item in items]
                total = sum(sizes) + sum(item.getSpaceAfter() for item in items)
                if total > available + .01:
                    raise ValueError(f"PDF {role} does not fit its reserved page margin.")
                y = height - settings["header_distance_mm"] * mm if role == "header" else settings["footer_distance_mm"] * mm + total
                for item, item_height in zip(items, sizes):
                    y -= item_height
                    item.drawOn(canvas, left, y)
                    y -= item.getSpaceAfter()
        finally:
            canvas.restoreState()

    output = BytesIO()
    document = BaseDocTemplate(output, pagesize=(width, height))
    frame = Frame(left, settings["margin_bottom_mm"] * mm, body_width, body_height,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    document.addPageTemplates(PageTemplate(id="HTML", frames=[frame], onPage=on_page))
    try:
        document.build(flowables(regions["main"], body_height) or [Spacer(1, 1)])
    except LayoutError as error:
        raise ValueError("PDF content does not fit the configured page dimensions.") from error
    return output.getvalue()
