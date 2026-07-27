import os
from collections.abc import Iterable
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .types import BlockType, BoundingBox, DocumentBlock, ParsedDocument

LABEL_MAP = {
    "doc_title": BlockType.TITLE,
    "paragraph_title": BlockType.HEADING,
    "section_title": BlockType.HEADING,
    "text": BlockType.PARAGRAPH,
    "content": BlockType.PARAGRAPH,
    "abstract": BlockType.PARAGRAPH,
    "list": BlockType.LIST,
    "figure": BlockType.FIGURE,
    "image": BlockType.FIGURE,
    "figure_title": BlockType.FIGURE_CAPTION,
    "table": BlockType.TABLE,
    "table_title": BlockType.TABLE_CAPTION,
    "table_footnote": BlockType.FOOTNOTE,
    "formula": BlockType.FORMULA,
    "formula_number": BlockType.FORMULA,
    "footnote": BlockType.FOOTNOTE,
    "reference": BlockType.REFERENCE,
}


def _result_payload(result: Any) -> dict[str, Any]:
    payload = getattr(result, "json", result)
    if callable(payload):
        payload = payload()
    if not isinstance(payload, dict):
        raise RuntimeError("PaddleOCR 返回了无法识别的结果格式")
    nested = payload.get("res")
    return nested if isinstance(nested, dict) else payload


def _bbox(coords: Any) -> BoundingBox:
    values = coords.tolist() if hasattr(coords, "tolist") else coords
    if (
        isinstance(values, list)
        and len(values) == 4
        and all(isinstance(value, (int, float)) for value in values)
    ):
        x0, y0, x1, y1 = values
    elif isinstance(values, list) and values and all(
        isinstance(point, list) and len(point) >= 2 for point in values
    ):
        xs = [float(point[0]) for point in values]
        ys = [float(point[1]) for point in values]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    else:
        x0, y0, x1, y1 = 0, 0, 1, 1
    return BoundingBox(x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1))


def _normalize_text(value: Any) -> str:
    text = str(value or "").replace("\u0000", "").strip()
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


class _TableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"}:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(_normalize_text("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None


def _normalize_table(value: Any) -> str:
    text = _normalize_text(value)
    if "<table" not in text.casefold():
        return text
    parser = _TableTextParser()
    parser.feed(text)
    return "\n".join(" | ".join(cell for cell in row if cell) for row in parser.rows) or text


class PaddleStructureParser:
    """Adapter around PP-StructureV3 with stable reading order and coordinates."""

    name = "paddleocr-ppstructurev3"

    def __init__(
        self,
        pipeline: Any | None = None,
        device: str = "cpu",
        model_source: str = "BOS",
    ) -> None:
        if pipeline is not None:
            self._pipeline = pipeline
            return
        os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", model_source)
        try:
            from paddleocr import PPStructureV3
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR 未安装。请在项目根目录执行 `uv sync --project backend` 后重试。"
            ) from exc
        try:
            import paddle  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "PaddlePaddle 推理引擎未安装。请执行 `uv sync --project backend` 后重试。"
            ) from exc
        try:
            self._pipeline = PPStructureV3(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                device=device,
                engine="paddle",
            )
        except Exception as exc:
            raise RuntimeError(f"PaddleOCR PP-StructureV3 初始化失败：{exc}") from exc

    @staticmethod
    def available() -> bool:
        try:
            import paddle  # noqa: F401
            import paddleocr  # noqa: F401
        except ImportError:
            return False
        return True

    def parse(self, pdf_path: Path) -> ParsedDocument:
        try:
            raw_results: Iterable[Any] = self._pipeline.predict(input=str(pdf_path))
        except Exception as exc:
            raise RuntimeError(f"PaddleOCR 识别失败：{exc}") from exc
        blocks: list[DocumentBlock] = []
        page_count = 0

        for result_index, result in enumerate(raw_results):
            payload = _result_payload(result)
            raw_page_index = payload.get("page_index")
            page_number = (
                int(raw_page_index) + 1 if raw_page_index is not None else result_index + 1
            )
            page_count = max(page_count, int(payload.get("page_count") or page_number))
            layout_items = payload.get("layout_det_res", {}).get("boxes", [])
            parsing_items = payload.get("parsing_res_list", [])
            items = parsing_items or layout_items
            for item in items:
                label = str(item.get("block_label") or item.get("label") or "text")
                content = (
                    item.get("block_content")
                    or item.get("text")
                    or item.get("content")
                    or ""
                )
                text = (
                    _normalize_table(content)
                    if label == "table"
                    else _normalize_text(content)
                )
                if not text:
                    continue
                coords = (
                    item.get("block_bbox")
                    if item.get("block_bbox") is not None
                    else item.get("coordinate")
                )
                blocks.append(
                    DocumentBlock(
                        page_number=page_number,
                        block_type=LABEL_MAP.get(label, BlockType.UNKNOWN),
                        reading_order=len(blocks),
                        text=text,
                        bbox=_bbox(coords),
                        confidence=item.get("score"),
                        parser=self.name,
                    )
                )

        if page_count == 0:
            raise RuntimeError("PaddleOCR 没有返回任何页面结果")
        if not blocks:
            raise RuntimeError("PaddleOCR 完成了页面处理，但没有识别到可阅读内容")
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
