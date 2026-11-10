from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel

from document_generation import generate_pdf


app = FastAPI(title="Customer Document API")


class PdfRequest(BaseModel):
    rendered_text: str
    customer_id: int


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
