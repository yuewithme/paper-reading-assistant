from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import create_database, session_dependency
from .models import Base, Paper
from .schemas import HealthResponse, PaperCreate, PaperResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    engine, session_factory = create_database(active_settings.database_url)
    Base.metadata.create_all(engine)

    app = FastAPI(
        title="论文辅助研读助手 API",
        version="0.1.0",
        description="Local-first API for bilingual paper reading and AI analysis.",
    )
    app.state.settings = active_settings
    app.state.engine = engine
    app.state.session_factory = session_factory

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

    return app


app = create_app()
