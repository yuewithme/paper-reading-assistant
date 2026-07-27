import re

from .parsing import BlockType

_LEGAL_NOTICE_PATTERNS = (
    r"\bprovided proper attribution\b",
    r"\bpermission to reproduce\b",
    r"\ball rights reserved\b",
    r"\bcopyright(?:ed)?\b",
    r"[©®]\s*\d{4}",
)
_AUTHOR_NOTE_PATTERNS = (
    r"\bequal contribution\b",
    r"\blisting order is random\b",
    r"\bwork performed while at\b",
    r"\bcorresponding author\b",
)
_FRONT_MATTER_HEADINGS = {
    "abstract",
    "摘要",
    "keywords",
    "keyword",
    "index terms",
}
_TAIL_HEADINGS = {
    "references",
    "reference",
    "bibliography",
    "acknowledgements",
    "acknowledgments",
}


def clean_extracted_text(text: str) -> str:
    """Normalize OCR whitespace and a few safe academic heading artifacts."""
    protected: list[str] = []

    def protect(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"PROTECTEDTOKEN{len(protected) - 1}PLACEHOLDER"

    cleaned = re.sub(
        r"https?://\S+|www\.\S+|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        protect,
        text,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.replace("\u00ad", "").replace("\u00a0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"(?<!\bi)(?<!\be)(?<=[a-z])\.(?=[a-z])", " ", cleaned)
    cleaned = re.sub(r"(?<=[A-Za-z])([,;:!?])(?=[A-Za-z])", r"\1 ", cleaned)
    cleaned = re.sub(r"(?<=[a-z])\.(?=[A-Z])", ". ", cleaned)
    cleaned = re.sub(r"^(\d+(?:\.\d+)*)([A-Z][A-Za-z])", r"\1 \2", cleaned)
    for index, original in enumerate(protected):
        cleaned = cleaned.replace(f"PROTECTEDTOKEN{index}PLACEHOLDER", original)
    return cleaned


def is_reader_noise(block_type: BlockType, text: str, page_number: int) -> bool:
    """Return true for metadata that should not enter translation or reading rows."""
    normalized = clean_extracted_text(text)
    lowered = normalized.casefold()
    if not normalized or block_type in {BlockType.FOOTNOTE, BlockType.REFERENCE}:
        return True
    if re.fullmatch(r"(?:page\s*)?\d{1,4}", lowered):
        return True
    if any(re.search(pattern, lowered) for pattern in _LEGAL_NOTICE_PATTERNS):
        return True
    if page_number == 1:
        if any(re.search(pattern, lowered) for pattern in _AUTHOR_NOTE_PATTERNS):
            return True
        email_count = len(re.findall(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", lowered))
        if email_count and len(normalized.split()) < 120:
            return True
    return False


def normalized_heading(text: str) -> str:
    heading = clean_extracted_text(text).casefold()
    heading = re.sub(r"^\d+(?:\.\d+)*\s*", "", heading)
    return re.sub(r"[^a-z\u4e00-\u9fff ]+", "", heading).strip()


def is_front_matter_heading(text: str) -> bool:
    return normalized_heading(text) in _FRONT_MATTER_HEADINGS


def is_tail_heading(text: str) -> bool:
    return normalized_heading(text) in _TAIL_HEADINGS


def is_substantive_analysis(texts: list[str]) -> bool:
    combined = " ".join(clean_extracted_text(text) for text in texts)
    word_count = len(re.findall(r"\b[\w'-]+\b", combined))
    return len(combined) >= 220 and word_count >= 35
