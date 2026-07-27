from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    title: Mapped[str] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(500))
    authors: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    paragraph_count: Mapped[int] = mapped_column(Integer, default=0)
    vocabulary_count: Mapped[int] = mapped_column(Integer, default=0)
    read_progress: Mapped[float] = mapped_column(Float, default=0)
    last_read_position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="created")
    translations_completed: Mapped[int] = mapped_column(Integer, default=0)
    analysis_group_count: Mapped[int] = mapped_column(Integer, default=0)
    analysis_groups_completed: Mapped[int] = mapped_column(Integer, default=0)
    ocr_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    translation_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ocr_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class DocumentBlockRecord(Base):
    __tablename__ = "document_blocks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    paper_id: Mapped[str] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"),
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer)
    block_type: Mapped[str] = mapped_column(String(40))
    reading_order: Mapped[int] = mapped_column(Integer)
    source_text: Mapped[str] = mapped_column(Text)
    bbox_json: Mapped[str] = mapped_column(Text, default="{}")
    parser: Mapped[str] = mapped_column(String(80))


class Paragraph(Base):
    __tablename__ = "paragraphs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    paper_id: Mapped[str] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"),
        index=True,
    )
    block_id: Mapped[str] = mapped_column(
        ForeignKey("document_blocks.id", ondelete="CASCADE"),
    )
    paragraph_index: Mapped[int] = mapped_column(Integer)
    source_text: Mapped[str] = mapped_column(Text)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int] = mapped_column(Integer)
    source_bbox_json: Mapped[str] = mapped_column(Text, default="{}")


class SemanticGroup(Base):
    __tablename__ = "semantic_groups"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    paper_id: Mapped[str] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"),
        index=True,
    )
    group_index: Mapped[int] = mapped_column(Integer)
    paragraph_ids_json: Mapped[str] = mapped_column(Text)
    analysis_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(40), default="pending")
    prompt_version: Mapped[str] = mapped_column(String(40), default="analysis-v1")


class VocabularyItem(Base):
    __tablename__ = "vocabulary_items"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    paper_id: Mapped[str] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"),
        index=True,
    )
    paragraph_id: Mapped[str | None] = mapped_column(
        ForeignKey("paragraphs.id", ondelete="SET NULL"),
        nullable=True,
    )
    normalized_text: Mapped[str] = mapped_column(String(500), index=True)
    display_text: Mapped[str] = mapped_column(String(500))
    contextual_translation: Mapped[str] = mapped_column(Text)
    source_sentence: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mastery_status: Mapped[str] = mapped_column(String(30), default="new")
    note: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(20), default="#f2d675")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    paper_id: Mapped[str] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), default="论文问答")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    selected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_paragraph_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    citations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
