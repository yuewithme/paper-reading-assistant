from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

from app.parsing import BlockType, DocumentParsingService


def create_native_pdf(path: Path) -> None:
    canvas = Canvas(str(path))
    canvas.setTitle("A Useful Paper")
    canvas.drawString(72, 760, "A Useful Paper")
    canvas.drawString(72, 720, "Abstract")
    canvas.drawString(
        72,
        690,
        "This paper presents a reliable parser for academic reading workflows.",
    )
    canvas.showPage()
    canvas.save()


def test_native_pdf_is_mapped_to_stable_document_model(tmp_path) -> None:
    pdf_path = tmp_path / "native.pdf"
    create_native_pdf(pdf_path)

    parsed = DocumentParsingService(minimum_native_characters_per_page=20).parse(pdf_path)

    assert parsed.parser == "pypdf"
    assert parsed.page_count == 1
    assert parsed.used_ocr is False
    assert any(block.block_type == BlockType.TITLE for block in parsed.blocks)
    assert "reliable parser" in parsed.text
    assert all(block.page_number == 1 for block in parsed.blocks)


def test_sparse_pdf_reports_ocr_fallback_requirement(tmp_path) -> None:
    pdf_path = tmp_path / "scan-like.pdf"
    canvas = Canvas(str(pdf_path))
    canvas.showPage()
    canvas.save()

    parsed = DocumentParsingService().parse(pdf_path)

    assert parsed.blocks == []
    assert any("PaddleOCR" in warning for warning in parsed.warnings)
