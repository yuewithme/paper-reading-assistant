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


class SemanticGroupResponse(BaseModel):
    id: str
    group_index: int
    paragraph_ids: list[str]
    analysis_text: str | None
    analysis_status: str


class AnalysisRequest(BaseModel):
    group_ids: list[str] | None = None
    force: bool = False


class AnalysisResponse(BaseModel):
    generated_count: int
    cached_count: int
    groups: list[SemanticGroupResponse]


class VocabularyCreate(BaseModel):
    selected_text: str = Field(min_length=1, max_length=500)
    paragraph_id: str | None = None
    contextual_translation: str | None = Field(default=None, max_length=2000)


class VocabularyUpdate(BaseModel):
    contextual_translation: str | None = Field(default=None, max_length=2000)
    mastery_status: str | None = Field(default=None, pattern="^(new|learning|mastered)$")
    note: str | None = Field(default=None, max_length=4000)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class VocabularyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    paper_id: str
    paragraph_id: str | None
    normalized_text: str
    display_text: str
    contextual_translation: str
    source_sentence: str
    page_number: int | None
    mastery_status: str
    note: str
    color: str
    created_at: datetime
