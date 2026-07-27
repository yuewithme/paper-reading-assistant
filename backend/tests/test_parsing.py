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
