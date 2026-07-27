import os
import re
from collections.abc import Iterable, Iterator
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
PDF_RENDER_SCALE = 2.0


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


def _order_page_blocks(blocks: list[DocumentBlock]) -> list[DocumentBlock]:
    """Recover column-major reading order when a page has two separated columns."""
    if len(blocks) < 4:
        return sorted(blocks, key=lambda block: (block.bbox.y0, block.bbox.x0))

    content_x0 = min(block.bbox.x0 for block in blocks)
    content_x1 = max(block.bbox.x1 for block in blocks)
    content_width = content_x1 - content_x0
    if content_width <= 0:
        return blocks
    midpoint = (content_x0 + content_x1) / 2

    narrow = [
        block
        for block in blocks
        if block.block_type != BlockType.TITLE
        and (block.bbox.x1 - block.bbox.x0) < content_width * 0.55
    ]
    left_candidates = [
        block
        for block in narrow
        if (block.bbox.x0 + block.bbox.x1) / 2 < midpoint
    ]
    right_candidates = [
        block
        for block in narrow
        if (block.bbox.x0 + block.bbox.x1) / 2 >= midpoint
    ]
    if len(left_candidates) < 2 or len(right_candidates) < 2:
        return sorted(blocks, key=lambda block: (block.bbox.y0, block.bbox.x0))

    left_edge = max(block.bbox.x1 for block in left_candidates)
    right_edge = min(block.bbox.x0 for block in right_candidates)
    if right_edge - left_edge < content_width * 0.03:
        return sorted(blocks, key=lambda block: (block.bbox.y0, block.bbox.x0))

    spanning = [
        block
        for block in blocks
        if block.bbox.x0 < left_edge and block.bbox.x1 > right_edge
    ]
    column_blocks = [block for block in blocks if block not in spanning]

    def column_major(items: list[DocumentBlock]) -> list[DocumentBlock]:
        left = [
            block
            for block in items
            if (block.bbox.x0 + block.bbox.x1) / 2 < midpoint
        ]
        right = [block for block in items if block not in left]

        def key(block: DocumentBlock) -> tuple[float, float]:
            return block.bbox.y0, block.bbox.x0

        return sorted(left, key=key) + sorted(right, key=key)

    ordered: list[DocumentBlock] = []
    remaining = list(column_blocks)
    for spanning_block in sorted(spanning, key=lambda block: (block.bbox.y0, block.bbox.x0)):
        before = [
            block
            for block in remaining
            if block.bbox.y1 <= spanning_block.bbox.y0
        ]
        ordered.extend(column_major(before))
        remaining = [block for block in remaining if block not in before]
        ordered.append(spanning_block)
    ordered.extend(column_major(remaining))
    return ordered


def _restore_reading_order(blocks: list[DocumentBlock]) -> list[DocumentBlock]:
    ordered: list[DocumentBlock] = []
    page_numbers = sorted({block.page_number for block in blocks})
    for page_number in page_numbers:
        page_blocks = [block for block in blocks if block.page_number == page_number]
        ordered.extend(_order_page_blocks(page_blocks))
    for index, block in enumerate(ordered):
        block.reading_order = index
    return ordered


_TITLE_BOILERPLATE = (
    "provided proper attribution",
    "permission to reproduce",
    "all rights reserved",
    "copyright",
    "preprint",
    "conference",
    "journalistic",
    "scholarly works",
)


def _select_document_title(blocks: list[DocumentBlock], fallback: str) -> str:
    """Choose a likely paper title while ignoring publication boilerplate."""
    candidates = [
        block.text.strip()
        for block in blocks
        if block.page_number == 1 and block.block_type == BlockType.TITLE
    ]
    for candidate in candidates:
        normalized = re.sub(r"\s+", " ", candidate).strip()
        lower = normalized.casefold()
        word_count = len(normalized.split())
        if not 3 <= word_count <= 30:
            continue
        if len(normalized) > 240 or "@" in normalized:
            continue
        if any(marker in lower for marker in _TITLE_BOILERPLATE):
            continue
        return normalized
    return fallback


class PaddleStructureParser:
    """Adapter around PP-StructureV3 with stable reading order and coordinates."""

    name = "paddleocr-ppstructurev3"

    def __init__(
        self,
        pipeline: Any | None = None,
        device: str = "cpu",
        model_source: str = "BOS",
        cpu_threads: int = 4,
        enable_hpi: bool = False,
        layout_model: str = "PP-DocLayout-M",
        text_detection_model: str = "PP-OCRv5_mobile_det",
        text_recognition_model: str = "en_PP-OCRv4_mobile_rec",
        formula_model: str = "PP-FormulaNet-S",
        table_structure_model: str = "SLANet_plus",
        use_region_detection: bool = False,
    ) -> None:
        self._render_pdf_pages = pipeline is None
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
                use_seal_recognition=False,
                use_chart_recognition=False,
                use_region_detection=use_region_detection,
                layout_detection_model_name=layout_model,
                text_detection_model_name=text_detection_model,
                text_recognition_model_name=text_recognition_model,
                formula_recognition_model_name=formula_model,
                wired_table_structure_recognition_model_name=table_structure_model,
                wireless_table_structure_recognition_model_name=table_structure_model,
                device=device,
                engine=None if enable_hpi else "paddle",
                enable_hpi=enable_hpi,
                cpu_threads=cpu_threads,
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

    def _page_inputs(self, pdf_path: Path) -> Iterator[tuple[int | None, int | None, Any]]:
        if not self._render_pdf_pages:
            yield None, None, str(pdf_path)
            return
        try:
            import numpy as np
            import pypdfium2 as pdfium
        except ImportError as exc:
            raise RuntimeError("PDF 逐页渲染依赖未安装") from exc
        document = pdfium.PdfDocument(str(pdf_path))
        try:
            page_count = len(document)
            for page_index in range(page_count):
                page = document[page_index]
                bitmap = page.render(scale=PDF_RENDER_SCALE)
                image = np.asarray(bitmap.to_pil().convert("RGB")).copy()
                bitmap.close()
                page.close()
                yield page_index + 1, page_count, image
        finally:
            document.close()

    def parse_pages(self, pdf_path: Path) -> Iterator[ParsedDocument]:
        predict = getattr(self._pipeline, "predict_iter", self._pipeline.predict)
        found_page = False
        result_index = 0
        try:
            for input_page_number, input_page_count, page_input in self._page_inputs(pdf_path):
                raw_results: Iterable[Any] = predict(input=page_input)
                for result in raw_results:
                    found_page = True
                    payload = _result_payload(result)
                    raw_page_index = payload.get("page_index")
                    page_number = input_page_number or (
                        int(raw_page_index) + 1
                        if raw_page_index is not None
                        else result_index + 1
                    )
                    page_count = input_page_count or max(
                        page_number,
                        int(payload.get("page_count") or page_number),
                    )
                    result_index += 1
                    layout_items = payload.get("layout_det_res", {}).get("boxes", [])
                    parsing_items = payload.get("parsing_res_list", [])
                    items = parsing_items or layout_items
                    blocks: list[DocumentBlock] = []
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
                    blocks = _restore_reading_order(blocks)
                    yield ParsedDocument(
                        title=_select_document_title(
                            blocks,
                            pdf_path.stem if page_number == 1 else "",
                        ),
                        page_count=page_count,
                        blocks=blocks,
                        parser=self.name,
                        used_ocr=True,
                    )
        except Exception as exc:
            raise RuntimeError(f"PaddleOCR 识别失败：{exc}") from exc

        if not found_page:
            raise RuntimeError("PaddleOCR 没有返回任何页面结果")

    def parse(self, pdf_path: Path) -> ParsedDocument:
        pages = list(self.parse_pages(pdf_path))
        blocks = [block for page in pages for block in page.blocks]
        if not blocks:
            raise RuntimeError("PaddleOCR 完成了页面处理，但没有识别到可阅读内容")
        blocks = _restore_reading_order(blocks)
        title = _select_document_title(blocks, pdf_path.stem)
        return ParsedDocument(
            title=title[:500],
            page_count=max(page.page_count for page in pages),
            blocks=blocks,
            parser=self.name,
            used_ocr=True,
        )
