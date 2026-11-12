import io

from PIL import Image

from app.api.routes.training import _simple_certificate_pdf
from app.services.onboarding import inspect_file
from app.services.training import QUESTIONS, randomized_order


def test_exam_has_fifty_questions_and_deterministic_order():
    assert len(QUESTIONS) == 50
    first = randomized_order("application:1")
    assert first == randomized_order("application:1")
    assert set(first) == set(QUESTIONS)


def test_document_quality_inspection_accepts_clear_image():
    image = Image.new("L", (800, 600), 255)
    for x in range(50, 750, 20):
        for y in range(50, 550):
            image.putpixel((x, y), 0)
    content = io.BytesIO()
    image.save(content, format="PNG")
    result = inspect_file(content.getvalue(), "image/png")
    assert result["width"] == 800
    assert result["height"] == 600
    assert "RESOLUTION_TOO_LOW" not in result["reasons"]


def test_certificate_pdf_is_structurally_complete():
    pdf = _simple_certificate_pdf(["Certificate", "PN-123"])
    assert pdf.startswith(b"%PDF-1.4")
    assert b"xref" in pdf
    assert pdf.endswith(b"%%EOF\n")
