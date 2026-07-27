from pathlib import Path
from typing import Protocol

from .types import ParsedDocument


class DocumentParser(Protocol):
    name: str

    def parse(self, pdf_path: Path) -> ParsedDocument:
        """Parse one PDF into the application's stable document model."""
