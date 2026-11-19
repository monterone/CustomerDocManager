"""PDF, RTF, and DOCX document generation."""

from io import BytesIO
from math import isfinite
from document_manager.paths import ASSETS_DIR

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def create_table_subdocument(document, columns, rows, style="Table Grid"):
    """{{p table}}."""
    if not columns:
        raise ValueError("At least one table column is required.")

    for column in columns:
        if not isinstance(column, dict):
            raise ValueError("Each column must define a key and a title.")
        if not isinstance(column.get("key"), str) or not column["key"].strip():
            raise ValueError("Each column must have a non-empty string key.")
        if not isinstance(column.get("title"), str):
            raise ValueError("Each column must have a string title.")

    subdocument = document.new_subdoc()
    table = subdocument.add_table(rows=1, cols=len(columns))
    table.style = style

    for index, column in enumerate(columns):
        table.rows[0].cells[index].text = column["title"]

    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each table row must be a dictionary.")

        cells = table.add_row().cells
        for index, column in enumerate(columns):
            value = row.get(column["key"])
            if value is None or (isinstance(value, str) and not value.strip()):
                cells[index].text = "None"
            else:
                cells[index].text = str(value)

    return subdocument


def generate_docx(template_file, values, tables=None, images=None):
    from docxtpl import DocxTemplate, InlineImage
    from docx.image.image import Image
    from docx.shared import Mm

    if not template_file:
        raise ValueError("The DOCX template file is empty.")

    document = DocxTemplate(BytesIO(template_file))
    field_names = document.get_undeclared_template_variables()
    if tables is None:
        tables = {}
    if images is None:
        images = {}

    conflicts = tables.keys() & images.keys()
    if conflicts:
        raise ValueError(f"Placeholders cannot be both tables and images: {', '.join(sorted(conflicts))}")
    unknown_images = images.keys() - field_names
    if unknown_images:
        raise ValueError(f"Image placeholders not found in template: {', '.join(sorted(unknown_images))}")

    unknown_tables = tables.keys() - field_names
    if unknown_tables:
        raise ValueError(
            f"Table placeholders not found in template: {', '.join(sorted(unknown_tables))}"
        )

    context = {}

    for name in field_names:
        if name in images:
            definition = images[name]
            try:
                data = bytes(definition["data"])
                image = Image.from_file(BytesIO(data))
                if image.content_type not in ("image/png", "image/jpeg"):
                    raise ValueError("Only PNG and JPEG images are supported.")
                if definition.get("mime_type", image.content_type) != image.content_type:
                    raise ValueError("The image format does not match its MIME type.")
                dimensions = {}
                for dimension in ("width", "height"):
                    size = definition.get(f"{dimension}_mm")
                    if size is not None:
                        size = float(size)
                        if not isfinite(size) or size <= 0:
                            raise ValueError("Image dimensions must be positive finite numbers.")
                        dimensions[dimension] = Mm(size)
                context[name] = InlineImage(document, BytesIO(data), **dimensions)
            except Exception as error:
                raise ValueError(f"Invalid image '{name}': {error}") from error
            continue

        if name in tables:
            definition = tables[name]
            if not isinstance(definition, dict) or not {"columns", "rows"} <= definition.keys():
                raise ValueError(f"Table '{name}' must define columns and rows.")
            context[name] = create_table_subdocument(
                document,
                definition["columns"],
                definition["rows"],
                style=definition.get("style", "Table Grid"),
            )
            continue

        value = values.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            context[name] = "None"
        else:
            context[name] = value

    document.render(context, autoescape=True)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def generate_pdf(rendered_text):
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)

    font_path = ASSETS_DIR / "fonts" / "NotoSansArmenian-Regular.ttf"
    font_bold_path = ASSETS_DIR / "fonts" / "NotoSansArmenian-Bold.ttf"

    pdfmetrics.registerFont(TTFont("NotoSansArmenian", str(font_path)))
    pdfmetrics.registerFont(TTFont("NotoSansArmenian-Bold", str(font_bold_path)))

    lines = rendered_text.splitlines()
    page_width, page_height = A4
    y_position = page_height - 72

    pdf.setFont("NotoSansArmenian-Bold", 16)
    pdf.drawString(72, y_position, lines[0] if lines else "Customer document")
    y_position -= 36

    pdf.setFont("NotoSansArmenian", 12)
    for line in lines[1:]:
        if line:
            pdf.drawString(72, y_position, line)
        y_position -= 24

    pdf.save()
    output.seek(0)
    return output.getvalue()


def escape_rtf(text):
    escaped_characters = []

    for character in text:
        codepoint = ord(character)

        if codepoint > 127:
            if codepoint <= 32767:
                escaped_characters.append(f"\\u{codepoint}?")
            else:
                escaped_characters.append(f"\\u{codepoint - 65536}?")
        elif character == "\\":
            escaped_characters.append("\\\\")
        elif character == "{":
            escaped_characters.append("\\{")
        elif character == "}":
            escaped_characters.append("\\}")
        elif character == "\n":
            escaped_characters.append("\\par\n")
        else:
            escaped_characters.append(character)

    return "".join(escaped_characters)


def generate_rtf(rendered_text):
    rtf_content = escape_rtf(rendered_text)
    rtf_document = (
        "{\\rtf1\\ansi\\deff0"
        "{\\fonttbl{\\f0 Arial;}}"
        "\\f0\\fs24 "
        + rtf_content
        + "}"
    )
    return rtf_document.encode("ascii")
