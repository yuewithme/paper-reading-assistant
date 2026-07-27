import hashlib
import json
import re
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .ai import AIConfigurationError, AIProvider, QwenProvider
from .config import Settings, get_settings
from .database import create_database, migrate_legacy_paper_table, session_dependency
from .models import (
    Base,
    Conversation,
    DocumentBlockRecord,
    Message,
    Paper,
    Paragraph,
    SemanticGroup,
    VocabularyItem,
)
from .parsing import BlockType, DocumentParsingService
from .schemas import (
    AnalysisRequest,
    AnalysisResponse,
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    HealthResponse,
    MessageResponse,
    PaperCreate,
    PaperDetailResponse,
    PaperResponse,
    ReadingProgressUpdate,
    SemanticGroupResponse,
    TranslationRequest,
    TranslationResponse,
    VocabularyCreate,
    VocabularyResponse,
    VocabularyUpdate,
)

READABLE_BLOCK_TYPES = {
    BlockType.TITLE,
    BlockType.HEADING,
    BlockType.PARAGRAPH,
    BlockType.LIST,
    BlockType.TABLE,
    BlockType.FIGURE_CAPTION,
    BlockType.TABLE_CAPTION,
    BlockType.FORMULA,
    BlockType.FOOTNOTE,
    BlockType.REFERENCE,
}
VOCABULARY_COLORS = ["#f2d675", "#9fd8c5", "#efb5c4", "#b8c7ef", "#d6b4e8", "#f0b98d"]


def normalize_vocabulary(text: str) -> str:
    compact = re.sub(r"\s+", " ", text.strip().casefold())
    compact = re.sub(r"^[^\w]+|[^\w]+$", "", compact)
    if " " in compact or len(compact) <= 3:
        return compact
    if compact.endswith("ies") and len(compact) > 4:
        return f"{compact[:-3]}y"
    if compact.endswith("ing") and len(compact) > 5:
        stem = compact[:-3]
        if len(stem) > 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if compact.endswith("ed") and len(compact) > 4:
        stem = compact[:-2]
        if len(stem) > 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if compact.endswith("es") and len(compact) > 4:
        return compact[:-2]
    if compact.endswith("s") and not compact.endswith("ss") and len(compact) > 3:
        return compact[:-1]
    return compact


def create_app(
    settings: Settings | None = None,
    ai_provider: AIProvider | None = None,
    document_parser: DocumentParsingService | None = None,
) -> FastAPI:
    active_settings = settings or get_settings()
    engine, session_factory = create_database(active_settings.database_url)
    Base.metadata.create_all(engine)
    migrate_legacy_paper_table(engine)
    active_settings.storage_path.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="论文辅助研读助手 API",
        version="1.0.0",
        description="Local-first API for bilingual paper reading and AI analysis.",
    )
    app.state.settings = active_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.ai_provider = ai_provider or QwenProvider(active_settings)
    app.state.document_parser = document_parser

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[active_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_session() -> Generator[Session, None, None]:
        yield from session_dependency(session_factory)

    SessionDependency = Annotated[Session, Depends(get_session)]

    def get_paper_or_404(paper_id: str, session: Session) -> Paper:
        paper = session.get(Paper, paper_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="论文不存在")
        return paper

    def parse_and_store(paper: Paper, session: Session, force_ocr: bool = False) -> None:
        if not paper.file_path:
            raise HTTPException(status_code=409, detail="这条论文记录没有 PDF 文件")
        paper.status = "processing"
        paper.error_message = None
        session.commit()
        try:
            if app.state.document_parser is None:
                from .parsing.paddle import PaddleStructureParser

                app.state.document_parser = DocumentParsingService(
                    parser=PaddleStructureParser(
                        device=active_settings.ocr_device,
                        model_source=active_settings.paddle_pdx_model_source,
                    )
                )
            parsed = app.state.document_parser.parse(
                Path(paper.file_path),
                force_ocr=force_ocr,
            )
            session.execute(
                delete(Paragraph).where(Paragraph.paper_id == paper.id)
            )
            session.execute(
                delete(DocumentBlockRecord).where(DocumentBlockRecord.paper_id == paper.id)
            )
            session.execute(
                delete(SemanticGroup).where(SemanticGroup.paper_id == paper.id)
            )
            paragraph_index = 0
            for block in parsed.blocks:
                record = DocumentBlockRecord(
                    paper_id=paper.id,
                    page_number=block.page_number,
                    block_type=block.block_type.value,
                    reading_order=block.reading_order,
                    source_text=block.text,
                    bbox_json=block.bbox.model_dump_json(),
                    parser=block.parser,
                )
                session.add(record)
                session.flush()
                if block.block_type in READABLE_BLOCK_TYPES:
                    session.add(
                        Paragraph(
                            paper_id=paper.id,
                            block_id=record.id,
                            paragraph_index=paragraph_index,
                            source_text=block.text,
                            page_number=block.page_number,
                            source_bbox_json=block.bbox.model_dump_json(),
                        )
                    )
                    paragraph_index += 1
            paper.title = parsed.title or paper.title
            paper.page_count = parsed.page_count
            paper.paragraph_count = paragraph_index
            paper.status = "ocr_complete" if paragraph_index else "failed"
            paper.error_message = "\n".join(parsed.warnings) or None
            session.commit()
            session.refresh(paper)
        except Exception as exc:
            session.rollback()
            paper = session.get(Paper, paper.id)
            if paper is not None:
                paper.status = "failed"
                paper.error_message = str(exc)
                session.commit()
            raise HTTPException(status_code=422, detail=f"PDF 解析失败：{exc}") from exc

    def process_paper_background(paper_id: str, force_ocr: bool = False) -> None:
        session = session_factory()
        try:
            paper = session.get(Paper, paper_id)
            if paper is not None:
                parse_and_store(paper, session, force_ocr=force_ocr)
                enrich_paper(paper.id, session)
        except HTTPException:
            # parse_and_store has already persisted the actionable failure state.
            pass
        finally:
            session.close()

    def process_enrichment_background(paper_id: str) -> None:
        session = session_factory()
        try:
            enrich_paper(paper_id, session)
        finally:
            session.close()

    def serialize_group(group: SemanticGroup) -> SemanticGroupResponse:
        return SemanticGroupResponse(
            id=group.id,
            group_index=group.group_index,
            paragraph_ids=json.loads(group.paragraph_ids_json),
            analysis_text=group.analysis_text,
            analysis_status=group.analysis_status,
        )

    def ensure_semantic_groups(paper_id: str, session: Session) -> list[SemanticGroup]:
        existing = list(
            session.scalars(
                select(SemanticGroup)
                .where(SemanticGroup.paper_id == paper_id)
                .order_by(SemanticGroup.group_index)
            )
        )
        if existing:
            return existing
        paragraphs = list(
            session.scalars(
                select(Paragraph)
                .where(Paragraph.paper_id == paper_id)
                .order_by(Paragraph.paragraph_index)
            )
        )
        block_ids = [paragraph.block_id for paragraph in paragraphs]
        block_types = {
            block.id: block.block_type
            for block in session.scalars(
                select(DocumentBlockRecord).where(DocumentBlockRecord.id.in_(block_ids))
            )
        }
        batches: list[list[str]] = []
        current: list[str] = []
        for paragraph in paragraphs:
            is_heading = block_types.get(paragraph.block_id) in {
                BlockType.TITLE.value,
                BlockType.HEADING.value,
            }
            if is_heading and current:
                batches.append(current)
                current = []
            current.append(paragraph.id)
            if is_heading or len(current) >= 3:
                batches.append(current)
                current = []
        if current:
            batches.append(current)
        groups = [
            SemanticGroup(
                paper_id=paper_id,
                group_index=index,
                paragraph_ids_json=json.dumps(paragraph_ids),
            )
            for index, paragraph_ids in enumerate(batches)
        ]
        session.add_all(groups)
        session.commit()
        return groups

    def translate_paragraphs(
        paper_id: str,
        session: Session,
        paragraph_ids: list[str] | None = None,
        force: bool = False,
    ) -> tuple[int, int, list[Paragraph]]:
        query = (
            select(Paragraph)
            .where(Paragraph.paper_id == paper_id)
            .order_by(Paragraph.paragraph_index)
        )
        if paragraph_ids:
            query = query.where(Paragraph.id.in_(paragraph_ids))
        paragraphs = list(session.scalars(query))
        translated_count = 0
        cached_count = 0
        for paragraph in paragraphs:
            if paragraph.translated_text and not force:
                cached_count += 1
                continue
            paragraph.translated_text = app.state.ai_provider.translate(
                paragraph.source_text
            )
            translated_count += 1
            session.commit()
        return translated_count, cached_count, paragraphs

    def analyze_groups(
        paper_id: str,
        session: Session,
        group_ids: list[str] | None = None,
        force: bool = False,
    ) -> tuple[int, int, list[SemanticGroup]]:
        groups = ensure_semantic_groups(paper_id, session)
        if group_ids:
            selected_ids = set(group_ids)
            groups = [group for group in groups if group.id in selected_ids]
        paragraphs = {
            paragraph.id: paragraph
            for paragraph in session.scalars(
                select(Paragraph).where(Paragraph.paper_id == paper_id)
            )
        }
        generated_count = 0
        cached_count = 0
        for group in groups:
            if group.analysis_text and not force:
                cached_count += 1
                continue
            paragraph_ids = json.loads(group.paragraph_ids_json)
            source = "\n\n".join(
                paragraphs[paragraph_id].source_text
                for paragraph_id in paragraph_ids
                if paragraph_id in paragraphs
            )
            group.analysis_status = "processing"
            session.commit()
            group.analysis_text = app.state.ai_provider.analyze(source)
            group.analysis_status = "ready"
            generated_count += 1
            session.commit()
        return generated_count, cached_count, groups

    def enrich_paper(paper_id: str, session: Session) -> None:
        paper = get_paper_or_404(paper_id, session)
        if not active_settings.auto_translate and not active_settings.auto_analyze:
            paper.status = "ready"
            session.commit()
            return
        paper.status = "enriching"
        paper.error_message = None
        session.commit()
        try:
            if active_settings.auto_translate:
                translate_paragraphs(paper_id, session)
            if active_settings.auto_analyze:
                analyze_groups(paper_id, session)
        except AIConfigurationError as exc:
            session.rollback()
            paper = get_paper_or_404(paper_id, session)
            paper.status = "ai_configuration_required"
            paper.error_message = str(exc)
            session.commit()
            return
        except Exception as exc:
            session.rollback()
            paper = get_paper_or_404(paper_id, session)
            paper.status = "ai_failed"
            paper.error_message = f"自动生成失败：{exc}"
            session.commit()
            return
        paper.status = "ready"
        paper.error_message = None
        session.commit()

    def serialize_message(message: Message) -> MessageResponse:
        return MessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            selected_text=message.selected_text,
            source_paragraph_ids=json.loads(message.source_paragraph_ids_json),
            citations=json.loads(message.citations_json),
            created_at=message.created_at,
        )

    def get_or_create_conversation(paper_id: str, session: Session) -> Conversation:
        conversation = session.scalar(
            select(Conversation).where(Conversation.paper_id == paper_id)
        )
        if conversation is None:
            conversation = Conversation(paper_id=paper_id)
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
        return conversation

    def serialize_conversation(
        conversation: Conversation,
        session: Session,
    ) -> ConversationResponse:
        messages = list(
            session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at)
            )
        )
        return ConversationResponse(
            id=conversation.id,
            paper_id=conversation.paper_id,
            title=conversation.title,
            messages=[serialize_message(message) for message in messages],
        )

    def retrieve_context(
        paper_id: str,
        question: str,
        selected_text: str | None,
        paragraph_id: str | None,
        session: Session,
    ) -> list[Paragraph]:
        paragraphs = list(
            session.scalars(
                select(Paragraph)
                .where(Paragraph.paper_id == paper_id)
                .order_by(Paragraph.paragraph_index)
            )
        )
        by_id = {paragraph.id: paragraph for paragraph in paragraphs}
        selected_indexes: set[int] = set()
        if paragraph_id and paragraph_id in by_id:
            index = by_id[paragraph_id].paragraph_index
            selected_indexes.update({index - 1, index, index + 1})

        query_tokens = {
            token
            for token in re.findall(
                r"[a-zA-Z][a-zA-Z-]{2,}|[\u4e00-\u9fff]{2,}",
                f"{question} {selected_text or ''}".casefold(),
            )
            if token not in {"what", "why", "how", "this", "that", "with", "from"}
        }
        scored: list[tuple[int, int]] = []
        for paragraph in paragraphs:
            searchable = f"{paragraph.source_text} {paragraph.translated_text or ''}".casefold()
            score = sum(1 for token in query_tokens if token in searchable)
            if score:
                scored.append((score, paragraph.paragraph_index))
        selected_indexes.update(index for _, index in sorted(scored, reverse=True)[:4])
        valid_indexes = {index for index in selected_indexes if 0 <= index < len(paragraphs)}
        if not valid_indexes:
            valid_indexes = set(range(min(3, len(paragraphs))))
        return [paragraphs[index] for index in sorted(valid_indexes)][:8]

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            service="paper-reading-assistant-api",
            version=app.version,
            environment=active_settings.app_env,
            llm_provider="qwen",
            llm_configured=active_settings.llm_configured,
        )

    @app.get("/api/papers", response_model=list[PaperResponse])
    def list_papers(session: SessionDependency) -> list[Paper]:
        return list(session.scalars(select(Paper).order_by(Paper.created_at.desc())))

    @app.post(
        "/api/papers",
        response_model=PaperResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_paper(payload: PaperCreate, session: SessionDependency) -> Paper:
        paper = Paper(title=payload.title.strip(), file_name=payload.file_name.strip())
        session.add(paper)
        session.commit()
        session.refresh(paper)
        return paper

    @app.post(
        "/api/papers/import",
        response_model=PaperResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def import_paper(
        session: SessionDependency,
        background_tasks: BackgroundTasks,
        file: Annotated[UploadFile, File()],
        background: bool = False,
    ) -> Paper:
        if not file.filename or not file.filename.casefold().endswith(".pdf"):
            raise HTTPException(status_code=415, detail="只支持 PDF 文件")
        content = await file.read(active_settings.max_pdf_size_mb * 1024 * 1024 + 1)
        if len(content) > active_settings.max_pdf_size_mb * 1024 * 1024:
            raise HTTPException(status_code=413, detail="PDF 文件过大")
        if not content.startswith(b"%PDF"):
            raise HTTPException(status_code=415, detail="文件不是有效 PDF")
        file_hash = hashlib.sha256(content).hexdigest()
        duplicate = session.scalar(select(Paper).where(Paper.file_hash == file_hash))
        if duplicate is not None:
            raise HTTPException(
                status_code=409,
                detail={"message": "这篇论文已经导入", "paper_id": duplicate.id},
            )

        paper_id = str(uuid4())
        paper_dir = active_settings.storage_path / paper_id
        paper_dir.mkdir(parents=True, exist_ok=False)
        pdf_path = paper_dir / "source.pdf"
        pdf_path.write_bytes(content)
        paper = Paper(
            id=paper_id,
            title=Path(file.filename).stem,
            file_name=file.filename,
            file_path=str(pdf_path),
            file_hash=file_hash,
            status="queued",
        )
        session.add(paper)
        session.commit()
        session.refresh(paper)
        if background:
            background_tasks.add_task(process_paper_background, paper.id)
        else:
            parse_and_store(paper, session)
            enrich_paper(paper.id, session)
        return paper

    @app.get("/api/papers/{paper_id}", response_model=PaperDetailResponse)
    def get_paper(paper_id: str, session: SessionDependency) -> dict:
        paper = get_paper_or_404(paper_id, session)
        paragraphs = list(
            session.scalars(
                select(Paragraph)
                .where(Paragraph.paper_id == paper.id)
                .order_by(Paragraph.paragraph_index)
            )
        )
        payload = PaperResponse.model_validate(paper).model_dump()
        payload["paragraphs"] = paragraphs
        return payload

    @app.post(
        "/api/papers/{paper_id}/translate",
        response_model=TranslationResponse,
    )
    def translate_paper(
        paper_id: str,
        payload: TranslationRequest,
        session: SessionDependency,
    ) -> TranslationResponse:
        get_paper_or_404(paper_id, session)
        try:
            translated_count, cached_count, paragraphs = translate_paragraphs(
                paper_id,
                session,
                payload.paragraph_ids,
                payload.force,
            )
        except AIConfigurationError as exc:
            session.rollback()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            session.rollback()
            raise HTTPException(status_code=502, detail=f"翻译失败：{exc}") from exc
        return TranslationResponse(
            translated_count=translated_count,
            cached_count=cached_count,
            paragraphs=paragraphs,
        )

    @app.post("/api/papers/{paper_id}/enrich", response_model=PaperResponse)
    def enrich_paper_endpoint(
        paper_id: str,
        session: SessionDependency,
        background_tasks: BackgroundTasks,
        background: bool = False,
    ) -> Paper:
        paper = get_paper_or_404(paper_id, session)
        if paper.paragraph_count == 0:
            raise HTTPException(status_code=409, detail="论文尚未完成 OCR，不能生成 AI 内容")
        if background:
            paper.status = "enriching"
            paper.error_message = None
            session.commit()
            background_tasks.add_task(process_enrichment_background, paper.id)
        else:
            enrich_paper(paper.id, session)
        return paper

    @app.get(
        "/api/papers/{paper_id}/groups",
        response_model=list[SemanticGroupResponse],
    )
    def list_semantic_groups(
        paper_id: str,
        session: SessionDependency,
    ) -> list[SemanticGroupResponse]:
        get_paper_or_404(paper_id, session)
        return [serialize_group(group) for group in ensure_semantic_groups(paper_id, session)]

    @app.post(
        "/api/papers/{paper_id}/analysis",
        response_model=AnalysisResponse,
    )
    def generate_analysis(
        paper_id: str,
        payload: AnalysisRequest,
        session: SessionDependency,
    ) -> AnalysisResponse:
        get_paper_or_404(paper_id, session)
        try:
            generated_count, cached_count, groups = analyze_groups(
                paper_id,
                session,
                payload.group_ids,
                payload.force,
            )
        except AIConfigurationError as exc:
            session.rollback()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            session.rollback()
            raise HTTPException(status_code=502, detail=f"深度解读失败：{exc}") from exc
        return AnalysisResponse(
            generated_count=generated_count,
            cached_count=cached_count,
            groups=[serialize_group(group) for group in groups],
        )

    @app.get(
        "/api/papers/{paper_id}/vocabulary",
        response_model=list[VocabularyResponse],
    )
    def list_vocabulary(
        paper_id: str,
        session: SessionDependency,
    ) -> list[VocabularyItem]:
        get_paper_or_404(paper_id, session)
        return list(
            session.scalars(
                select(VocabularyItem)
                .where(VocabularyItem.paper_id == paper_id)
                .order_by(VocabularyItem.created_at.desc())
            )
        )

    @app.post(
        "/api/papers/{paper_id}/vocabulary",
        response_model=VocabularyResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_vocabulary(
        paper_id: str,
        payload: VocabularyCreate,
        session: SessionDependency,
    ) -> VocabularyItem:
        paper = get_paper_or_404(paper_id, session)
        normalized = normalize_vocabulary(payload.selected_text)
        if not normalized:
            raise HTTPException(status_code=422, detail="没有可收藏的文本")
        duplicate = session.scalar(
            select(VocabularyItem).where(
                VocabularyItem.paper_id == paper_id,
                VocabularyItem.normalized_text == normalized,
            )
        )
        if duplicate is not None:
            return duplicate
        paragraph = (
            session.get(Paragraph, payload.paragraph_id)
            if payload.paragraph_id
            else None
        )
        if paragraph is not None and paragraph.paper_id != paper_id:
            raise HTTPException(status_code=422, detail="段落不属于当前论文")
        contextual_translation = payload.contextual_translation
        if not contextual_translation:
            try:
                contextual_translation = app.state.ai_provider.translate(
                    f"请只翻译选中的词或短语：{payload.selected_text}\n"
                    f"论文语境：{paragraph.source_text if paragraph else ''}"
                )
            except AIConfigurationError:
                contextual_translation = "待补充释义"
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"划词翻译失败：{exc}") from exc
        # The list is intentionally small for a personal per-paper collection.
        color_index = len(
            list(
                session.scalars(
                    select(VocabularyItem).where(VocabularyItem.paper_id == paper_id)
                )
            )
        )
        item = VocabularyItem(
            paper_id=paper_id,
            paragraph_id=paragraph.id if paragraph else None,
            normalized_text=normalized,
            display_text=payload.selected_text.strip(),
            contextual_translation=contextual_translation,
            source_sentence=paragraph.source_text if paragraph else payload.selected_text.strip(),
            page_number=paragraph.page_number if paragraph else None,
            color=VOCABULARY_COLORS[color_index % len(VOCABULARY_COLORS)],
        )
        session.add(item)
        paper.vocabulary_count += 1
        session.commit()
        session.refresh(item)
        return item

    @app.patch(
        "/api/vocabulary/{item_id}",
        response_model=VocabularyResponse,
    )
    def update_vocabulary(
        item_id: str,
        payload: VocabularyUpdate,
        session: SessionDependency,
    ) -> VocabularyItem:
        item = session.get(VocabularyItem, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="词汇不存在")
        for name, value in payload.model_dump(exclude_none=True).items():
            setattr(item, name, value)
        session.commit()
        session.refresh(item)
        return item

    @app.delete("/api/vocabulary/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_vocabulary(item_id: str, session: SessionDependency) -> None:
        item = session.get(VocabularyItem, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="词汇不存在")
        paper = session.get(Paper, item.paper_id)
        session.delete(item)
        if paper is not None:
            paper.vocabulary_count = max(0, paper.vocabulary_count - 1)
        session.commit()

    @app.get(
        "/api/papers/{paper_id}/conversation",
        response_model=ConversationResponse,
    )
    def get_conversation(
        paper_id: str,
        session: SessionDependency,
    ) -> ConversationResponse:
        get_paper_or_404(paper_id, session)
        conversation = get_or_create_conversation(paper_id, session)
        return serialize_conversation(conversation, session)

    @app.post(
        "/api/papers/{paper_id}/chat",
        response_model=ChatResponse,
    )
    def chat_with_paper(
        paper_id: str,
        payload: ChatRequest,
        session: SessionDependency,
    ) -> ChatResponse:
        get_paper_or_404(paper_id, session)
        conversation = get_or_create_conversation(paper_id, session)
        context_paragraphs = retrieve_context(
            paper_id,
            payload.question,
            payload.selected_text,
            payload.paragraph_id,
            session,
        )
        existing_messages = list(
            session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at)
            )
        )
        history = [
            {"role": message.role, "content": message.content}
            for message in existing_messages[-10:]
            if message.role in {"user", "assistant"}
        ]
        context = "\n\n".join(
            (
                f"[段落 {paragraph.paragraph_index + 1}｜第 {paragraph.page_number} 页]\n"
                f"{paragraph.source_text}"
            )
            for paragraph in context_paragraphs
        )
        if payload.selected_text:
            context = f"[用户选中文本]\n{payload.selected_text}\n\n{context}"
        try:
            answer_text = app.state.ai_provider.answer(
                payload.question,
                context[:20000],
                history,
            )
        except AIConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"AI 问答失败：{exc}") from exc

        paragraph_ids = [paragraph.id for paragraph in context_paragraphs]
        citations = [
            {
                "paragraph_id": paragraph.id,
                "page_number": paragraph.page_number,
                "quote": paragraph.source_text[:220],
            }
            for paragraph in context_paragraphs[:4]
        ]
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=payload.question,
            selected_text=payload.selected_text,
            source_paragraph_ids_json=json.dumps(paragraph_ids),
        )
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer_text,
            source_paragraph_ids_json=json.dumps(paragraph_ids),
            citations_json=json.dumps(citations, ensure_ascii=False),
        )
        session.add_all([user_message, assistant_message])
        session.commit()
        session.refresh(assistant_message)
        conversation_payload = serialize_conversation(conversation, session)
        return ChatResponse(
            conversation=conversation_payload,
            answer=serialize_message(assistant_message),
        )

    @app.get("/api/papers/{paper_id}/file")
    def get_paper_file(paper_id: str, session: SessionDependency) -> FileResponse:
        paper = get_paper_or_404(paper_id, session)
        if not paper.file_path or not Path(paper.file_path).exists():
            raise HTTPException(status_code=404, detail="PDF 文件不存在")
        return FileResponse(
            paper.file_path,
            media_type="application/pdf",
            filename=paper.file_name,
        )

    @app.patch(
        "/api/papers/{paper_id}/progress",
        response_model=PaperResponse,
    )
    def update_reading_progress(
        paper_id: str,
        payload: ReadingProgressUpdate,
        session: SessionDependency,
    ) -> Paper:
        paper = get_paper_or_404(paper_id, session)
        paper.read_progress = payload.read_progress
        paper.last_read_position = payload.last_read_position
        session.commit()
        session.refresh(paper)
        return paper

    @app.post("/api/papers/{paper_id}/reparse", response_model=PaperResponse)
    def reparse_paper(
        paper_id: str,
        session: SessionDependency,
        background_tasks: BackgroundTasks,
        force_ocr: bool = False,
        background: bool = False,
    ) -> Paper:
        paper = get_paper_or_404(paper_id, session)
        if background:
            paper.status = "queued"
            paper.error_message = None
            session.commit()
            background_tasks.add_task(process_paper_background, paper.id, force_ocr)
        else:
            parse_and_store(paper, session, force_ocr=force_ocr)
            enrich_paper(paper.id, session)
        return paper

    @app.delete("/api/papers/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_paper(paper_id: str, session: SessionDependency) -> None:
        paper = get_paper_or_404(paper_id, session)
        paper_dir = Path(paper.file_path).parent if paper.file_path else None
        session.delete(paper)
        session.commit()
        if paper_dir and paper_dir.exists():
            shutil.rmtree(paper_dir)

    return app


app = create_app()
