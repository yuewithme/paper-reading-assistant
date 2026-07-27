from sqlalchemy import text

from app.database import create_database, migrate_legacy_paper_table


def test_migration_backfills_pages_for_completed_ocr_only(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine, _ = create_database(database_url)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE papers (
                    id VARCHAR(36) PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    file_name VARCHAR(500) NOT NULL,
                    status VARCHAR(40) NOT NULL,
                    page_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO papers (id, title, file_name, status, page_count)
                VALUES
                    ('ready-paper', 'Ready', 'ready.pdf', 'ready', 15),
                    ('active-paper', 'Active', 'active.pdf', 'processing', 15)
                """
            )
        )

    migrate_legacy_paper_table(engine)

    with engine.connect() as connection:
        rows = dict(
            connection.execute(
                text("SELECT id, pages_processed FROM papers ORDER BY id")
            ).all()
        )

    assert rows["ready-paper"] == 15
    assert rows["active-paper"] == 0
