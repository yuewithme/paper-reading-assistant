from pathlib import Path

from .paddle import PaddleStructureParser
from .types import ParsedDocument


class DocumentParsingService:
    """Parse every PDF through PaddleOCR's document-structure pipeline."""

    def __init__(self, parser: PaddleStructureParser | None = None) -> None:
        self.parser = parser

    def parse(self, pdf_path: Path, force_ocr: bool = False) -> ParsedDocument:
        # ``force_ocr`` is retained for API compatibility. OCR is now always used.
        del force_ocr
        parser = self.parser or PaddleStructureParser()
        return parser.parse(pdf_path)
