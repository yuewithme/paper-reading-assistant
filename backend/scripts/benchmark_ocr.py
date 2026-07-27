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
    document = document_parser.parse(args.pdf)
    print(
        json.dumps(
            {
                "seconds": round(perf_counter() - started, 3),
                "pages": document.page_count,
                "blocks": len(document.blocks),
                "title": document.title,
                "parser": document.parser,
                "preview": [
                    {
                        "page": block.page_number,
                        "type": block.block_type.value,
                        "text": block.text[:240],
                    }
                    for block in document.blocks[:12]
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
