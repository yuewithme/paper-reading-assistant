from app.content import (
    clean_extracted_text,
    is_front_matter_heading,
    is_reader_noise,
    is_substantive_analysis,
    is_tail_heading,
)
from app.parsing import BlockType


def test_academic_text_cleaning_normalizes_safe_ocr_artifacts() -> None:
    assert clean_extracted_text(
        "1Introduction\n  Attention.mechanism improves tasks,our evidence ; agrees."
    ) == (
        "1 Introduction Attention mechanism improves tasks, our evidence; agrees."
    )
    assert clean_extracted_text("Contact alice@example.com or https://example.com/a.b") == (
        "Contact alice@example.com or https://example.com/a.b"
    )


def test_reader_noise_removes_boilerplate_but_keeps_abstract_content() -> None:
    assert is_reader_noise(
        BlockType.PARAGRAPH,
        "Provided proper attribution is provided before reproducing these figures.",
        1,
    )
    assert is_reader_noise(
        BlockType.PARAGRAPH,
        "Alice alice@example.com Bob bob@example.com University Lab",
        1,
    )
    assert is_reader_noise(BlockType.REFERENCE, "Smith et al. A useful paper.", 12)
    assert not is_reader_noise(
        BlockType.PARAGRAPH,
        "We propose a transformer based entirely on attention mechanisms.",
        1,
    )


def test_analysis_boundaries_identify_front_matter_tail_and_short_content() -> None:
    assert is_front_matter_heading("Abstract")
    assert is_front_matter_heading("Keywords")
    assert is_tail_heading("12 References")
    assert not is_substantive_analysis(["A short and obvious sentence."])
    assert is_substantive_analysis(
        [
            "The proposed architecture replaces recurrent computation with self-attention, "
            "which allows every token to interact directly with every other token in a layer. "
            "This removes the sequential dependency that previously limited parallel training. "
            "The authors then evaluate both translation quality and computational efficiency "
            "to show that the architectural change improves accuracy while reducing training cost."
        ]
    )
