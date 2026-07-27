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
    last_read_position: str | None = None
    error_message: str | None = None
    translations_completed: int = 0
    analysis_group_count: int = 0
    analysis_groups_completed: int = 0
    ocr_duration_seconds: float | None = None
    translation_duration_seconds: float | None = None
    analysis_duration_seconds: float | None = None
    total_duration_seconds: float | None = None
    processing_started_at: datetime | None = None
    ocr_completed_at: datetime | None = None
    processing_completed_at: datetime | None = None
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


class CitationResponse(BaseModel):
    paragraph_id: str
    page_number: int
    quote: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    selected_text: str | None
    source_paragraph_ids: list[str]
    citations: list[CitationResponse]
    created_at: datetime


class ConversationResponse(BaseModel):
    id: str
    paper_id: str
    title: str
    messages: list[MessageResponse]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    selected_text: str | None = Field(default=None, max_length=8000)
    paragraph_id: str | None = None


class ChatResponse(BaseModel):
    conversation: ConversationResponse
    answer: MessageResponse


class ReadingProgressUpdate(BaseModel):
    read_progress: float = Field(ge=0, le=1)
    last_read_position: str | None = Field(default=None, max_length=100)
