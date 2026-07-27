from pathlib import Path

from .native import NativePdfParser
from .paddle import PaddleStructureParser
from .types import ParsedDocument


class DocumentParsingService:
    def __init__(self, minimum_native_characters_per_page: int = 80) -> None:
        self.minimum_native_characters_per_page = minimum_native_characters_per_page
        self.native_parser = NativePdfParser()

    def parse(self, pdf_path: Path, force_ocr: bool = False) -> ParsedDocument:
        if force_ocr:
            return PaddleStructureParser().parse(pdf_path)

        native_result = self.native_parser.parse(pdf_path)
        character_count = sum(len(block.text) for block in native_result.blocks)
        threshold = native_result.page_count * self.minimum_native_characters_per_page
        if character_count >= threshold:
            return native_result

        if PaddleStructureParser.available():
            return PaddleStructureParser().parse(pdf_path)

        native_result.warnings.append(
            "文本层内容不足，但 PaddleOCR 尚未安装；已保留原生解析结果。"
        )
        return native_result
