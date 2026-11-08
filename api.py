from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


app = FastAPI(title="Customer Document API")


class PdfRequest(BaseModel):
    rendered_text: str
    customer_id: int


def generate_pdf(rendered_text):
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)

    fonts_dir = Path(__file__).parent / "assets" / "fonts"
    font_path = fonts_dir / "NotoSansArmenian-Regular.ttf"
    font_bold_path = fonts_dir / "NotoSansArmenian-Bold.ttf"

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
    return output.getvalue()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/documents/pdf")
def create_pdf(request: PdfRequest):
    pdf_data = generate_pdf(request.rendered_text)
    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="customer_{request.customer_id}.pdf"'
            )
        },
    )
