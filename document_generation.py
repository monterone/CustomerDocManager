"""PDF, RTF, and DOCX document generation."""

from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def generate_docx(template_file, values):
    from docxtpl import DocxTemplate

    if not template_file:
        raise ValueError("The DOCX template file is empty.")

    document = DocxTemplate(BytesIO(template_file))
    field_names = document.get_undeclared_template_variables()
    context = {}

    for name in field_names:
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

    font_path = Path(__file__).parent / "assets" / "fonts" / "NotoSansArmenian-Regular.ttf"
    font_bold_path = Path(__file__).parent / "assets" / "fonts" / "NotoSansArmenian-Bold.ttf"

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
