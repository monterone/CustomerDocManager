"""Direct RTF export for our controlled HTML document format."""

import re

from document_manager.documents.images import prepare_image
from document_manager.documents.html_document import HtmlElement, get_table_rows, iter_inline_tokens, parse_html_document, validate_page_settings


_ALIGNMENTS = {"left": r"\ql", "center": r"\qc", "right": r"\qr", "justify": r"\qj"}
_PARAGRAPHS = {"p": (0, 22), "h1": (1, 36), "h2": (2, 28), "h3": (3, 24)}
_PAGE_CONTROLS = {
    "page_width_mm": "paperw", "page_height_mm": "paperh",
    "margin_top_mm": "margt", "margin_bottom_mm": "margb",
    "margin_left_mm": "margl", "margin_right_mm": "margr",
    "header_distance_mm": "headery", "footer_distance_mm": "footery",
}


def _escape_text(text):
    """Encode Unicode as signed UTF-16 RTF escapes, including surrogate pairs."""
    try:
        encoded = text.encode("utf-16-le")
    except UnicodeEncodeError as error:
        raise ValueError("Text contains an invalid Unicode surrogate.") from error
    parts = []
    for offset in range(0, len(encoded), 2):
        unit = int.from_bytes(encoded[offset:offset + 2], "little")
        if unit < 32 or unit == 127:
            raise ValueError("Text contains an unsupported control character.")
        if unit > 127:
            signed = unit if unit < 32768 else unit - 65536
            parts.append(f"\\u{signed}?")
        elif chr(unit) in "\\{}":
            parts.append("\\" + chr(unit))
        else:
            parts.append(chr(unit))
    return "".join(parts)


def _page_dimensions(settings):
    dimensions = {}
    for name, value in settings.items():
        try:
            twips = round(value * 1440 / 25.4)
        except OverflowError as error:
            raise ValueError(f"Page setting {name} is too large for RTF.") from error
        if twips > 2147483647:
            raise ValueError(f"Page setting {name} is too large for RTF.")
        dimensions[name] = twips
    if dimensions["page_width_mm"] <= dimensions["margin_left_mm"] + dimensions["margin_right_mm"]:
        raise ValueError("Page margins leave no body width after rounding to RTF units.")
    if dimensions["page_height_mm"] <= dimensions["margin_top_mm"] + dimensions["margin_bottom_mm"]:
        raise ValueError("Page margins leave no body height after rounding to RTF units.")
    return dimensions


def _page_controls(dimensions):
    controls = "".join(f"\\{_PAGE_CONTROLS[name]}{value}" for name, value in dimensions.items())
    if dimensions["page_width_mm"] > dimensions["page_height_mm"]:
        controls += r"\landscape"
    return controls


def _image(attributes, assets, width, height):
    image = prepare_image(attributes, assets, width * 25.4 / 1440, height * 25.4 / 1440)
    display_width = round(image.width_mm * 1440 / 25.4)
    display_height = round(image.height_mm * 1440 / 25.4)
    if display_width <= 0 or display_height <= 0:
        raise ValueError("Image dimensions are too small for RTF.")
    kind = "pngblip" if image.mime_type == "image/png" else "jpegblip"
    picture = (f"{{\\pict\\{kind}\\picw{image.pixel_width}\\pich{image.pixel_height}"
               f"\\picwgoal{display_width}\\pichgoal{display_height}")
    if image.alt:
        picture += r"{\*\picprop{\sp{\sn wzDescription}{\sv " + _escape_text(image.alt) + "}}}"
    hexadecimal = image.data.hex()
    return picture + "\n" + "\n".join(hexadecimal[i:i + 128] for i in range(0, len(hexadecimal), 128)) + "}"


def _paragraph(element, assets, width, height, role="main", in_cell=False,
               end_paragraph=True, bold=False):
    style, size = _PARAGRAPHS.get(element.tag, (0, 22))
    if style == 0 and role != "main":
        style, size = (4, 20) if role == "header" else (5, 20)
    alignment = _ALIGNMENTS[element.attrs.get("data-align", "left")]
    table_controls = r"\intbl\itap1" if in_cell else ""
    parts = [f"{{\\pard\\plain\\s{style}{alignment}{table_controls}\\f0\\fs{size}\\sb0\\sa120 "]
    has_text = pending_space = False
    for kind, text, bold, italic, underline in iter_inline_tokens(element, bold=bold or style in (1, 2, 3)):
        if kind in {"img", "span"}:
            if pending_space and has_text:
                parts.append(" ")
            parts.append(_image(text, assets, width, height) if kind == "img"
                         else r"{\field{\*\fldinst PAGE}{\fldrslt 1}}")
            has_text, pending_space = True, False
            continue
        if kind == "br":
            parts.append(r"\line ")
            has_text = pending_space = False
            continue
        if kind != "text":
            raise ValueError(f"RTF export does not support inline <{kind}> elements yet.")
        text = re.sub(r"[ \t\r\n\f]+", " ", text)
        content = text.strip(" ")
        if not content:
            pending_space = pending_space or bool(text)
            continue
        if has_text and (pending_space or text.startswith(" ")):
            parts.append(" ")
        formatting = f"\\b{int(bold)}\\i{int(italic)}" + (r"\ul" if underline else r"\ulnone")
        parts.append("{" + formatting + " " + _escape_text(content) + "}")
        has_text, pending_space = True, text.endswith(" ")
    parts.append(r"\par}" if end_paragraph else "}")
    return "".join(parts)


def _table(element, assets, width, height):
    rows = get_table_rows(element)
    count = len(rows[0].children)
    boundaries = [round(width * index / count) for index in range(count + 1)]
    padding = round(2 * 1440 / 25.4)
    parts = []
    for row_index, row in enumerate(rows):
        parts.append(r"{\trowd\trleft0\trgaph0\trautofit0\trrh0")
        parts.append(f"\\trpaddl{padding}\\trpaddr{padding}\\trpaddt0\\trpaddb0"
                     r"\trpaddfl3\trpaddfr3\trpaddft3\trpaddfb3")
        if row_index == 0 and all(cell.tag == "th" for cell in row.children):
            parts.append(r"\trhdr")
        for right in boundaries[1:]:
            for edge in ("t", "b", "l", "r"):
                parts.append(f"\\clbrdr{edge}\\brdrs\\brdrw10")
            parts.append(f"\\cellx{right}")
        for index, cell in enumerate(row.children):
            cell_width = boundaries[index + 1] - boundaries[index] - padding * 2
            if cell_width <= 0:
                raise ValueError("Table columns leave no cell content width.")
            paragraphs = [child for child in cell.children if isinstance(child, HtmlElement) and child.tag == "p"]
            paragraphs = paragraphs or [cell]
            for paragraph_index, paragraph in enumerate(paragraphs):
                parts.append(_paragraph(paragraph, assets, cell_width, height, in_cell=True,
                                        end_paragraph=paragraph_index != len(paragraphs) - 1,
                                        bold=cell.tag == "th"))
            parts.append(r"\cell ")
        parts.append(r"\row}")
    return "\n".join(parts)


def _region(region, assets, width, height, role):
    parts = []
    for index, element in enumerate(region.children):
        if element.tag == "table":
            if index and region.children[index - 1].tag == "table":
                parts.append(r"{\pard\plain\s0\f0\fs2\sb0\sa0\par}")
            parts.append(_table(element, assets, width, height))
        else:
            parts.append(_paragraph(element, assets, width, height, role=role))
    if role != "main" and region.children and region.children[-1].tag == "table":
        parts.append(r"{\pard\plain\s0\f0\fs2\sb0\sa0\par}")
    return "\n".join(parts)


def export_html_to_rtf(html, page_settings=None, assets=None):
    """Return filled RTF bytes, including native tables, pictures, and page regions."""
    regions = parse_html_document(html)
    settings = validate_page_settings(page_settings)
    dimensions = _page_dimensions(settings)
    if assets is None:
        assets = {}
    if not isinstance(assets, dict):
        raise ValueError("Image assets must be a dictionary keyed by internal references.")
    width = dimensions["page_width_mm"] - dimensions["margin_left_mm"] - dimensions["margin_right_mm"]
    height = dimensions["page_height_mm"] - dimensions["margin_top_mm"] - dimensions["margin_bottom_mm"]
    stylesheet = [r"{\stylesheet{\s0\f0\fs22 Normal;}"]
    for level, size in ((1, 36), (2, 28), (3, 24)):
        stylesheet.append(f"{{\\s{level}\\sbasedon0\\snext0\\keepn\\outlinelevel{level - 1}\\f0\\fs{size}\\b Heading {level};}}")
    stylesheet.extend([r"{\s4\sbasedon0\f0\fs20 Header;}", r"{\s5\sbasedon0\f0\fs20 Footer;}", "}"])
    content = []
    for role in ("header", "footer"):
        if role in regions and regions[role].children:
            content.append("{\\" + role + " " + _region(regions[role], assets, width, height, role) + "}")
    content.append(_region(regions["main"], assets, width, height, "main"))
    document = (r"{\rtf1\ansi\ansicpg1252\deff0\uc1"
                r"{\fonttbl{\f0\fnil\fcharset0 Arial;}}"
                + "".join(stylesheet) + _page_controls(dimensions)
                + "\n" + "\n".join(content) + "}")
    return document.encode("ascii")
