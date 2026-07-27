import re
from pathlib import Path

from pypdf import PdfReader

from .types import BlockType, BoundingBox, DocumentBlock, ParsedDocument

HEADING_PATTERN = re.compile(
    r"^(?:\d+(?:\.\d+)*\s+)?(?:abstract|introduction|related work|methods?|"
    r"results?|discussion|conclusion|references)\b",
    re.IGNORECASE,
)


def _paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    chunks = re.split(r"\n\s*\n|(?<=[.!?])\n(?=[A-Z0-9])", normalized)
    result: list[str] = []
    for chunk in chunks:
        compact = re.sub(r"[ \t]+", " ", chunk).strip()
        compact = re.sub(r"(?<=\w)-\n(?=\w)", "", compact)
        compact = re.sub(r"\n+", " ", compact)
        if compact:
            result.append(compact)
    return result


def _classify(text: str, page_number: int, order: int) -> BlockType:
    lowered = text.casefold()
    if page_number == 1 and order == 0 and len(text) < 220:
        return BlockType.TITLE
    if HEADING_PATTERN.match(text) or (len(text) < 90 and text.isupper()):
        return BlockType.HEADING
    if lowered.startswith(("figure ", "fig. ")):
        return BlockType.FIGURE_CAPTION
    if lowered.startswith("table "):
        return BlockType.TABLE_CAPTION
    if re.fullmatch(r"[\W\d_a-zA-Z=+\-*/^(){}\[\] ]{4,}", text) and "=" in text:
        return BlockType.FORMULA
    if lowered.startswith("references"):
        return BlockType.REFERENCE
    return BlockType.PARAGRAPH


class NativePdfParser:
    name = "pypdf"

    def parse(self, pdf_path: Path) -> ParsedDocument:
        reader = PdfReader(str(pdf_path))
        blocks: list[DocumentBlock] = []
        warnings: list[str] = []

        for page_index, page in enumerate(reader.pages):
            extracted = page.extract_text(extraction_mode="layout") or ""
            page_paragraphs = _paragraphs(extracted)
            if not page_paragraphs:
                warnings.append(f"第 {page_index + 1} 页未提取到有效文本")
            for order, text in enumerate(page_paragraphs):
                blocks.append(
                    DocumentBlock(
                        page_number=page_index + 1,
                        block_type=_classify(text, page_index + 1, order),
                        reading_order=len(blocks),
                        text=text,
                        bbox=BoundingBox(),
                        parser=self.name,
                    )
                )

        title_block = next(
            (block for block in blocks if block.block_type == BlockType.TITLE),
            None,
        )
        return ParsedDocument(
            title=title_block.text[:500] if title_block else pdf_path.stem,
            page_count=len(reader.pages),
            blocks=blocks,
            parser=self.name,
            warnings=warnings,
        )
