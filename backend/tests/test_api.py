from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def build_client(tmp_path) -> TestClient:
    database_path = tmp_path / "test.db"
    settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{database_path.as_posix()}",
        dashscope_api_key=None,
    )
    return TestClient(create_app(settings))


def test_health_reports_qwen_configuration_state(tmp_path) -> None:
    client = build_client(tmp_path)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "paper-reading-assistant-api",
        "version": "0.1.0",
        "environment": "test",
        "llm_provider": "qwen",
        "llm_configured": False,
    }


def test_paper_can_be_created_and_listed(tmp_path) -> None:
    client = build_client(tmp_path)

    create_response = client.post(
        "/api/papers",
        json={"title": "Attention Is All You Need", "file_name": "attention.pdf"},
    )
    list_response = client.get("/api/papers")

    assert create_response.status_code == 201
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["title"] == "Attention Is All You Need"

