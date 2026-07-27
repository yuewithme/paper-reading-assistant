import hashlib
import json
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .ai import AIConfigurationError, AIProvider, QwenProvider
from .config import Settings, get_settings
from .database import create_database, migrate_legacy_paper_table, session_dependency
from .models import Base, DocumentBlockRecord, Paper, Paragraph, SemanticGroup
from .parsing import BlockType, DocumentParsingService
from .schemas import (
    AnalysisRequest,
    AnalysisResponse,
    HealthResponse,
    PaperCreate,
    PaperDetailResponse,
    PaperResponse,
    SemanticGroupResponse,
    TranslationRequest,
    TranslationResponse,
)

READABLE_BLOCK_TYPES = {
    BlockType.TITLE,
    BlockType.HEADING,
    BlockType.PARAGRAPH,
    BlockType.LIST,
    BlockType.FIGURE_CAPTION,
    BlockType.TABLE_CAPTION,
    BlockType.FORMULA,
}


def create_app(
    settings: Settings | None = None,
    ai_provider: AIProvider | None = None,
) -> FastAPI:
    active_settings = settings or get_settings()
    engine, session_factory = create_database(active_settings.database_url)
    Base.metadata.create_all(engine)
    migrate_legacy_paper_table(engine)
    active_settings.storage_path.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="论文辅助研读助手 API",
        version="0.2.0",
        description="Local-first API for bilingual paper reading and AI analysis.",
    )
    app.state.settings = active_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.ai_provider = ai_provider or QwenProvider(active_settings)

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
            parsed = DocumentParsingService().parse(Path(paper.file_path), force_ocr=force_ocr)
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
            paper.status = "ready" if paragraph_index else "needs_ocr"
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
        file: Annotated[UploadFile, File()],
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
        parse_and_store(paper, session)
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
        query = (
            select(Paragraph)
            .where(Paragraph.paper_id == paper_id)
            .order_by(Paragraph.paragraph_index)
        )
        if payload.paragraph_ids:
            query = query.where(Paragraph.id.in_(payload.paragraph_ids))
        paragraphs = list(session.scalars(query))
        translated_count = 0
        cached_count = 0
        try:
            for paragraph in paragraphs:
                if paragraph.translated_text and not payload.force:
                    cached_count += 1
                    continue
                paragraph.translated_text = app.state.ai_provider.translate(
                    paragraph.source_text
                )
                translated_count += 1
                session.commit()
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
        groups = ensure_semantic_groups(paper_id, session)
        if payload.group_ids:
            selected_ids = set(payload.group_ids)
            groups = [group for group in groups if group.id in selected_ids]
        paragraphs = {
            paragraph.id: paragraph
            for paragraph in session.scalars(
                select(Paragraph).where(Paragraph.paper_id == paper_id)
            )
        }
        generated_count = 0
        cached_count = 0
        try:
            for group in groups:
                if group.analysis_text and not payload.force:
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

    @app.post("/api/papers/{paper_id}/reparse", response_model=PaperResponse)
    def reparse_paper(
        paper_id: str,
        session: SessionDependency,
        force_ocr: bool = False,
    ) -> Paper:
        paper = get_paper_or_404(paper_id, session)
        parse_and_store(paper, session, force_ocr=force_ocr)
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
