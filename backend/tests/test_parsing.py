import sys
from io import BytesIO
from types import ModuleType

from reportlab.pdfgen.canvas import Canvas

from app.parsing import BlockType, DocumentParsingService
from app.parsing.paddle import PaddleStructureParser


class FakeResult:
    json = {
        "res": {
            "page_index": 0,
            "page_count": 1,
            "parsing_res_list": [
                {
                    "block_bbox": [[30, 20], [570, 20], [570, 80], [30, 80]],
                    "block_label": "doc_title",
                    "block_content": "A Useful Paper",
                    "block_order": 0,
                },
                {
                    "block_bbox": [30, 110, 570, 155],
                    "block_label": "paragraph_title",
                    "block_content": "Abstract",
                    "block_order": 1,
                },
                {
                    "block_bbox": [30, 170, 570, 320],
                    "block_label": "text",
                    "block_content": (
                        "This paper presents a reliable parser for academic reading workflows."
                    ),
                    "block_order": 2,
                },
                {
                    "block_bbox": [30, 340, 570, 440],
                    "block_label": "table",
                    "block_content": (
                        "<table><tr><th>Method</th><th>Score</th></tr>"
                        "<tr><td>Ours</td><td>0.91</td></tr></table>"
                    ),
                    "block_order": 3,
                },
            ],
        }
    }


class FakePipeline:
    def predict(self, input: str):
        assert input.endswith(".pdf")
        return [FakeResult()]


def test_balanced_cpu_profile_uses_lightweight_models(monkeypatch) -> None:
    captured: dict = {}

    class FakePPStructureV3:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_paddleocr = ModuleType("paddleocr")
    fake_paddleocr.PPStructureV3 = FakePPStructureV3
    monkeypatch.setitem(sys.modules, "paddleocr", fake_paddleocr)
    monkeypatch.setitem(sys.modules, "paddle", ModuleType("paddle"))

    PaddleStructureParser()

    assert captured["cpu_threads"] == 4
    assert captured["enable_hpi"] is False
    assert captured["engine"] == "paddle"
    assert captured["layout_detection_model_name"] == "PP-DocLayout-M"
    assert captured["text_detection_model_name"] == "PP-OCRv5_mobile_det"
    assert captured["text_recognition_model_name"] == "en_PP-OCRv4_mobile_rec"
    assert captured["formula_recognition_model_name"] == "PP-FormulaNet-S"
    assert captured["wired_table_structure_recognition_model_name"] == "SLANet_plus"
    assert captured["wireless_table_structure_recognition_model_name"] == "SLANet_plus"
    assert captured["use_region_detection"] is False


def test_paddle_result_is_mapped_to_stable_document_model(tmp_path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    parser = PaddleStructureParser(pipeline=FakePipeline())

    parsed = DocumentParsingService(parser=parser).parse(pdf_path)

    assert parsed.parser == "paddleocr-ppstructurev3"
    assert parsed.page_count == 1
    assert parsed.used_ocr is True
    assert any(block.block_type == BlockType.TITLE for block in parsed.blocks)
    assert any(block.block_type == BlockType.TABLE for block in parsed.blocks)
    assert "reliable parser" in parsed.text
    assert "Method | Score\nOurs | 0.91" in parsed.text
    assert all(block.page_number == 1 for block in parsed.blocks)
    assert parsed.blocks[0].bbox.x1 == 570
    assert all(block.parser == "paddleocr-ppstructurev3" for block in parsed.blocks)


def test_paddle_pages_are_yielded_incrementally(tmp_path) -> None:
    class IterPipeline:
        def predict(self, input: str):
            raise AssertionError("parse_pages should prefer predict_iter")

        def predict_iter(self, input: str):
            assert input.endswith(".pdf")
            for page_index in range(2):
                yield {
                    "res": {
                        "page_index": page_index,
                        "page_count": 2,
                        "parsing_res_list": [
                            {
                                "block_bbox": [30, 20, 570, 80],
                                "block_label": "doc_title" if page_index == 0 else "text",
                                "block_content": (
                                    "A Streaming Paper"
                                    if page_index == 0
                                    else "Second page content."
                                ),
                            }
                        ],
                    }
                }

    pdf_path = tmp_path / "streaming.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")

    pages = list(PaddleStructureParser(pipeline=IterPipeline()).parse_pages(pdf_path))

    assert len(pages) == 2
    assert pages[0].title == "A Streaming Paper"
    assert pages[0].blocks[0].page_number == 1
    assert pages[1].blocks[0].page_number == 2


def test_pdf_is_rendered_and_sent_to_paddle_one_page_at_a_time(tmp_path) -> None:
    class ImagePipeline:
        def __init__(self) -> None:
            self.calls = 0

        def predict(self, input):
            raise AssertionError("page rendering should use predict_iter")

        def predict_iter(self, input):
            self.calls += 1
            assert input.ndim == 3
            assert input.shape[2] == 3
            yield {
                "res": {
                    "page_index": 0,
                    "page_count": 1,
                    "parsing_res_list": [
                        {
                            "block_bbox": [30, 20, 570, 80],
                            "block_label": "text",
                            "block_content": f"Rendered page {self.calls}",
                        }
                    ],
                }
            }

    buffer = BytesIO()
    canvas = Canvas(buffer)
    canvas.drawString(72, 760, "Page one")
    canvas.showPage()
    canvas.drawString(72, 760, "Page two")
    canvas.showPage()
    canvas.save()
    pdf_path = tmp_path / "two-pages.pdf"
    pdf_path.write_bytes(buffer.getvalue())
    pipeline = ImagePipeline()
    parser = PaddleStructureParser(pipeline=pipeline)
    parser._render_pdf_pages = True

    pages = list(parser.parse_pages(pdf_path))

    assert pipeline.calls == 2
    assert [page.blocks[0].page_number for page in pages] == [1, 2]
    assert [page.page_count for page in pages] == [2, 2]


def test_publication_boilerplate_is_not_selected_as_document_title(tmp_path) -> None:
    class BoilerplateResult:
        json = {
            "res": {
                "page_index": 0,
                "page_count": 1,
                "parsing_res_list": [
                    {
                        "block_bbox": [245, 142, 974, 224],
                        "block_label": "doc_title",
                        "block_content": (
                            "Provided proper attribution is provided, Google hereby grants "
                            "permission to reproduce the tables and figures in this paper "
                            "solely for use in journalistic or scholarly works."
                        ),
                    },
                    {
                        "block_bbox": [419, 295, 797, 325],
                        "block_label": "doc_title",
                        "block_content": "Attention Is All You Need",
                    },
                ],
            }
        }

    class BoilerplatePipeline:
        def predict(self, input: str):
            return [BoilerplateResult()]

    pdf_path = tmp_path / "1706.03762v7.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")

    parsed = PaddleStructureParser(pipeline=BoilerplatePipeline()).parse(pdf_path)

    assert parsed.title == "Attention Is All You Need"


def test_paddle_empty_result_is_an_actionable_failure(tmp_path) -> None:
    class EmptyPipeline:
        def predict(self, input: str):
            return [{"res": {"page_index": 0, "page_count": 1, "parsing_res_list": []}}]

    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    parser = PaddleStructureParser(pipeline=EmptyPipeline())

    try:
        parser.parse(pdf_path)
    except RuntimeError as exc:
        assert "没有识别到可阅读内容" in str(exc)
    else:
        raise AssertionError("empty OCR output should fail explicitly")


def test_two_column_page_is_reordered_column_first(tmp_path) -> None:
    class TwoColumnResult:
        json = {
            "res": {
                "page_index": 0,
                "page_count": 1,
                "parsing_res_list": [
                    {
                        "block_bbox": [280, 50, 720, 90],
                        "block_label": "doc_title",
                        "block_content": "Full-width title",
                    },
                    {
                        "block_bbox": [50, 120, 120, 145],
                        "block_label": "paragraph_title",
                        "block_content": "Abstract",
                    },
                    {
                        "block_bbox": [550, 120, 650, 145],
                        "block_label": "paragraph_title",
                        "block_content": "2. Results",
                    },
                    {
                        "block_bbox": [50, 160, 450, 260],
                        "block_label": "text",
                        "block_content": "Left column introduction.",
                    },
                    {
                        "block_bbox": [550, 160, 950, 260],
                        "block_label": "text",
                        "block_content": "Right column results.",
                    },
                    {
                        "block_bbox": [50, 300, 150, 325],
                        "block_label": "paragraph_title",
                        "block_content": "1. Method",
                    },
                    {
                        "block_bbox": [50, 340, 450, 440],
                        "block_label": "text",
                        "block_content": "Left column method.",
                    },
                    {
                        "block_bbox": [550, 300, 950, 440],
                        "block_label": "table",
                        "block_content": "Right column table.",
                    },
                ],
            }
        }

    class TwoColumnPipeline:
        def predict(self, input: str):
            return [TwoColumnResult()]

    pdf_path = tmp_path / "columns.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    parsed = PaddleStructureParser(pipeline=TwoColumnPipeline()).parse(pdf_path)

    assert [block.text for block in parsed.blocks] == [
        "Full-width title",
        "Abstract",
        "Left column introduction.",
        "1. Method",
        "Left column method.",
        "2. Results",
        "Right column results.",
        "Right column table.",
    ]
    assert [block.reading_order for block in parsed.blocks] == list(range(8))
