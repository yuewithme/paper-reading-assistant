import argparse
import json
from pathlib import Path
from time import perf_counter

from app.config import get_settings
from app.parsing.paddle import PaddleStructureParser


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the configured PaddleOCR profile.")
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()

    settings = get_settings()
    document_parser = PaddleStructureParser(
        device=settings.ocr_device,
        model_source=settings.paddle_pdx_model_source,
        cpu_threads=settings.ocr_cpu_threads,
        enable_hpi=settings.ocr_enable_hpi,
        layout_model=settings.ocr_layout_model,
        text_detection_model=settings.ocr_text_detection_model,
        text_recognition_model=settings.ocr_text_recognition_model,
        formula_model=settings.ocr_formula_model,
        table_structure_model=settings.ocr_table_structure_model,
        use_region_detection=settings.ocr_use_region_detection,
    )
    started = perf_counter()
    pages = []
    first_page_seconds = None
    for page in document_parser.parse_pages(args.pdf):
        pages.append(page)
        if first_page_seconds is None:
            first_page_seconds = round(perf_counter() - started, 3)
    blocks = [block for page in pages for block in page.blocks]
    print(
        json.dumps(
            {
                "seconds": round(perf_counter() - started, 3),
                "first_page_seconds": first_page_seconds,
                "pages": max(page.page_count for page in pages),
                "blocks": len(blocks),
                "title": next((page.title for page in pages if page.title), args.pdf.stem),
                "parser": document_parser.name,
                "preview": [
                    {
                        "page": block.page_number,
                        "type": block.block_type.value,
                        "text": block.text[:240],
                    }
                    for block in blocks[:12]
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
