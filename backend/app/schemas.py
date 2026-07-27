from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    service: str
    version: str
    environment: str
    llm_provider: str
    llm_configured: bool


class PaperCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    file_name: str = Field(min_length=1, max_length=500)


class PaperResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    file_name: str
    status: str
    page_count: int = 0
    paragraph_count: int = 0
    vocabulary_count: int = 0
    read_progress: float = 0
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ParagraphResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    paragraph_index: int
    source_text: str
    translated_text: str | None
    page_number: int
    source_bbox_json: str


class PaperDetailResponse(PaperResponse):
    paragraphs: list[ParagraphResponse]


class TranslationRequest(BaseModel):
    paragraph_ids: list[str] | None = None
    force: bool = False


class TranslationResponse(BaseModel):
    translated_count: int
    cached_count: int
    paragraphs: list[ParagraphResponse]
