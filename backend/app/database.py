from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker


def ensure_sqlite_directory(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return

    raw_path = database_url.removeprefix(prefix)
    if raw_path == ":memory:":
        return

    Path(raw_path).parent.mkdir(parents=True, exist_ok=True)


def create_database(database_url: str) -> tuple[Engine, sessionmaker[Session]]:
    ensure_sqlite_directory(database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, session_factory


def migrate_legacy_paper_table(engine: Engine) -> None:
    """Add phase-one columns to databases created by the stage-zero prototype."""
    inspector = inspect(engine)
    if "papers" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("papers")}
    additions = {
        "authors": "TEXT",
        "year": "INTEGER",
        "file_path": "VARCHAR(1000)",
        "file_hash": "VARCHAR(64)",
        "page_count": "INTEGER NOT NULL DEFAULT 0",
        "pages_processed": "INTEGER NOT NULL DEFAULT 0",
        "paragraph_count": "INTEGER NOT NULL DEFAULT 0",
        "vocabulary_count": "INTEGER NOT NULL DEFAULT 0",
        "read_progress": "FLOAT NOT NULL DEFAULT 0",
        "last_read_position": "VARCHAR(100)",
        "error_message": "TEXT",
        "translations_completed": "INTEGER NOT NULL DEFAULT 0",
        "analysis_group_count": "INTEGER NOT NULL DEFAULT 0",
        "analysis_groups_completed": "INTEGER NOT NULL DEFAULT 0",
        "ocr_duration_seconds": "FLOAT",
        "translation_duration_seconds": "FLOAT",
        "analysis_duration_seconds": "FLOAT",
        "total_duration_seconds": "FLOAT",
        "processing_started_at": "DATETIME",
        "ocr_completed_at": "DATETIME",
        "processing_completed_at": "DATETIME",
        "updated_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, sql_type in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE papers ADD COLUMN {name} {sql_type}"))
        connection.execute(
            text(
                """
                UPDATE papers
                SET pages_processed = page_count
                WHERE pages_processed = 0
                  AND page_count > 0
                  AND status IN (
                      'ocr_complete',
                      'enriching',
                      'ai_configuration_required',
                      'ai_failed',
                      'ready'
                  )
                """
            )
        )


def session_dependency(
    session_factory: sessionmaker[Session],
) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
