from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .types import BlockType, BoundingBox, DocumentBlock, ParsedDocument

LABEL_MAP = {
    "doc_title": BlockType.TITLE,
    "paragraph_title": BlockType.HEADING,
    "text": BlockType.PARAGRAPH,
    "figure": BlockType.FIGURE,
    "figure_title": BlockType.FIGURE_CAPTION,
    "table": BlockType.TABLE,
    "table_title": BlockType.TABLE_CAPTION,
    "formula": BlockType.FORMULA,
    "reference": BlockType.REFERENCE,
}


class PaddleStructureParser:
    """Thin adapter around PP-StructureV3.

    PaddleOCR is optional because its runtime and model files are large. The
    adapter keeps those details outside the rest of the application.
    """

    name = "paddleocr-ppstructurev3"

    def __init__(self) -> None:
        try:
            from paddleocr import PPStructureV3
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR 未安装。请执行 `uv sync --extra ocr` 后重试。"
            ) from exc
        self._pipeline = PPStructureV3()

    @staticmethod
    def available() -> bool:
        try:
            import paddleocr  # noqa: F401
        except ImportError:
            return False
        return True

    def parse(self, pdf_path: Path) -> ParsedDocument:
        raw_results: Iterable[Any] = self._pipeline.predict(input=str(pdf_path))
        blocks: list[DocumentBlock] = []
        page_count = 0

        for page_index, result in enumerate(raw_results, start=1):
            page_count = page_index
            payload = getattr(result, "json", result)
            if callable(payload):
                payload = payload()
            if isinstance(payload, dict) and "res" in payload:
                payload = payload["res"]
            layout_items = payload.get("layout_det_res", {}).get("boxes", [])
            parsing_items = payload.get("parsing_res_list", [])
            items = parsing_items or layout_items
            for item in items:
                text = str(
                    item.get("block_content")
                    or item.get("text")
                    or item.get("content")
                    or ""
                ).strip()
                if not text:
                    continue
                coords = item.get("coordinate") or item.get("bbox") or [0, 0, 1, 1]
                label = str(item.get("block_label") or item.get("label") or "text")
                blocks.append(
                    DocumentBlock(
                        page_number=page_index,
                        block_type=LABEL_MAP.get(label, BlockType.UNKNOWN),
                        reading_order=len(blocks),
                        text=text,
                        bbox=BoundingBox(
                            x0=float(coords[0]),
                            y0=float(coords[1]),
                            x1=float(coords[2]),
                            y1=float(coords[3]),
                        ),
                        confidence=item.get("score"),
                        parser=self.name,
                    )
                )

        if page_count == 0:
            raise RuntimeError("PaddleOCR 没有返回任何页面结果")
        title = next(
            (block.text for block in blocks if block.block_type == BlockType.TITLE),
            pdf_path.stem,
        )
        return ParsedDocument(
            title=title[:500],
            page_count=page_count,
            blocks=blocks,
            parser=self.name,
            used_ocr=True,
        )
