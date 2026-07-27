from enum import StrEnum

from pydantic import BaseModel, Field


class BlockType(StrEnum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    FIGURE = "figure"
    FIGURE_CAPTION = "figure_caption"
    TABLE = "table"
    TABLE_CAPTION = "table_caption"
    FORMULA = "formula"
    FOOTNOTE = "footnote"
    REFERENCE = "reference"
    UNKNOWN = "unknown"


class BoundingBox(BaseModel):
    x0: float = 0
    y0: float = 0
    x1: float = 1
    y1: float = 1


class DocumentBlock(BaseModel):
    page_number: int = Field(ge=1)
    block_type: BlockType = BlockType.PARAGRAPH
    reading_order: int = Field(ge=0)
    text: str
    bbox: BoundingBox = Field(default_factory=BoundingBox)
    confidence: float | None = Field(default=None, ge=0, le=1)
    parser: str


class ParsedDocument(BaseModel):
    title: str
    page_count: int = Field(ge=1)
    blocks: list[DocumentBlock]
    parser: str
    used_ocr: bool = False
    warnings: list[str] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks if block.text.strip())
