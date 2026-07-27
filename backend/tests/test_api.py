from io import BytesIO
from threading import Lock
from time import sleep

from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas

from app.config import Settings
from app.main import create_app
from app.parsing import BlockType, BoundingBox, DocumentBlock, ParsedDocument


class FakeAIProvider:
    def translate(self, text: str) -> str:
        return f"译文：{text}"

    def analyze(self, text: str) -> str:
        return f"深度解读：{text}"

    def answer(
        self,
        question: str,
        context: str,
        history: list[dict[str, str]],
    ) -> str:
        return f"回答：{question}（上下文 {len(context)} 字，历史 {len(history)} 条）"


class ConcurrencyTrackingProvider(FakeAIProvider):
    def __init__(self) -> None:
        self._lock = Lock()
        self._translation_active = 0
        self._analysis_active = 0
        self.max_translation_active = 0
        self.max_analysis_active = 0

    def translate(self, text: str) -> str:
        with self._lock:
            self._translation_active += 1
            self.max_translation_active = max(
                self.max_translation_active,
                self._translation_active,
            )
        sleep(0.03)
        with self._lock:
            self._translation_active -= 1
        return super().translate(text)

    def analyze(self, text: str) -> str:
        with self._lock:
            self._analysis_active += 1
            self.max_analysis_active = max(
                self.max_analysis_active,
                self._analysis_active,
            )
        sleep(0.03)
        with self._lock:
            self._analysis_active -= 1
        return super().analyze(text)


class FakeDocumentParser:
    def parse(self, _pdf_path, force_ocr: bool = False) -> ParsedDocument:
        del force_ocr
        texts = [
            (BlockType.TITLE, "Reliable Academic Reading"),
            (BlockType.HEADING, "Abstract"),
            (
                BlockType.PARAGRAPH,
                "This paper describes a structured workflow for understanding research.",
            ),
        ]
        return ParsedDocument(
            title="Reliable Academic Reading",
            page_count=1,
            blocks=[
                DocumentBlock(
                    page_number=1,
                    block_type=block_type,
                    reading_order=index,
                    text=text,
                    bbox=BoundingBox(x0=72, y0=80 + index * 40, x1=520, y1=110 + index * 40),
                    confidence=0.99,
                    parser="paddleocr-ppstructurev3",
                )
                for index, (block_type, text) in enumerate(texts)
            ],
            parser="paddleocr-ppstructurev3",
            used_ocr=True,
        )


DEFAULT_FAKE_AI = object()


def build_client(tmp_path, ai_provider=DEFAULT_FAKE_AI) -> TestClient:
    database_path = tmp_path / "test.db"
    settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{database_path.as_posix()}",
        dashscope_api_key=None,
        storage_path=tmp_path / "papers",
    )
    provider = FakeAIProvider() if ai_provider is DEFAULT_FAKE_AI else ai_provider
    return TestClient(
        create_app(
            settings,
            ai_provider=provider,
            document_parser=FakeDocumentParser(),
        )
    )


def test_health_reports_qwen_configuration_state(tmp_path) -> None:
    client = build_client(tmp_path)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "paper-reading-assistant-api",
        "version": "1.0.0",
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


def make_pdf() -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer)
    canvas.drawString(72, 760, "Reliable Academic Reading")
    canvas.drawString(72, 720, "Abstract")
    canvas.drawString(
        72,
        690,
        "This paper describes a structured workflow for understanding research.",
    )
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def test_pdf_import_persists_file_and_paragraphs(tmp_path) -> None:
    client = build_client(tmp_path)

    response = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", make_pdf(), "application/pdf")},
    )

    assert response.status_code == 201
    paper = response.json()
    assert paper["status"] == "ready"
    assert paper["page_count"] == 1
    assert paper["paragraph_count"] > 0
    assert paper["translations_completed"] == paper["paragraph_count"]
    assert paper["analysis_group_count"] > 0
    assert paper["analysis_groups_completed"] == paper["analysis_group_count"]
    assert paper["ocr_duration_seconds"] is not None
    assert paper["translation_duration_seconds"] is not None
    assert paper["analysis_duration_seconds"] is not None
    assert paper["total_duration_seconds"] is not None
    assert paper["processing_started_at"] is not None
    assert paper["ocr_completed_at"] is not None
    assert paper["processing_completed_at"] is not None

    detail = client.get(f"/api/papers/{paper['id']}").json()
    assert detail["paragraphs"]
    assert detail["paragraphs"][0]["page_number"] == 1
    assert client.get(f"/api/papers/{paper['id']}/file").status_code == 200


def test_duplicate_pdf_is_rejected_and_delete_removes_record(tmp_path) -> None:
    client = build_client(tmp_path)
    pdf = make_pdf()
    first = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", pdf, "application/pdf")},
    )
    duplicate = client.post(
        "/api/papers/import",
        files={"file": ("copy.pdf", pdf, "application/pdf")},
    )

    assert duplicate.status_code == 409
    paper_id = first.json()["id"]
    assert client.delete(f"/api/papers/{paper_id}").status_code == 204
    assert client.get(f"/api/papers/{paper_id}").status_code == 404


def test_translation_is_generated_once_and_then_read_from_cache(tmp_path) -> None:
    client = build_client(tmp_path, ai_provider=FakeAIProvider())
    imported = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", make_pdf(), "application/pdf")},
    ).json()

    detail = client.get(f"/api/papers/{imported['id']}").json()
    first = client.post(f"/api/papers/{imported['id']}/translate", json={})

    assert all(
        paragraph["translated_text"].startswith("译文：")
        for paragraph in detail["paragraphs"]
    )
    assert first.status_code == 200
    assert first.json()["translated_count"] == 0
    assert first.json()["cached_count"] == imported["paragraph_count"]


def test_translation_without_key_reports_configuration_action(tmp_path) -> None:
    client = build_client(tmp_path, ai_provider=None)
    imported = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", make_pdf(), "application/pdf")},
    ).json()

    response = client.post(f"/api/papers/{imported['id']}/translate", json={})

    assert response.status_code == 503
    assert "DASHSCOPE_API_KEY" in response.json()["detail"]
    assert imported["status"] == "ai_configuration_required"

    client.app.state.ai_provider = FakeAIProvider()
    resumed = client.post(f"/api/papers/{imported['id']}/enrich")
    detail = client.get(f"/api/papers/{imported['id']}").json()

    assert resumed.status_code == 200
    assert detail["status"] == "ready"
    assert all(paragraph["translated_text"] for paragraph in detail["paragraphs"])


def test_semantic_groups_and_deep_analysis_are_cached(tmp_path) -> None:
    client = build_client(tmp_path, ai_provider=FakeAIProvider())
    imported = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", make_pdf(), "application/pdf")},
    ).json()

    groups = client.get(f"/api/papers/{imported['id']}/groups")
    first = client.post(f"/api/papers/{imported['id']}/analysis", json={})

    assert groups.status_code == 200
    assert groups.json()
    assert all(1 <= len(group["paragraph_ids"]) <= 4 for group in groups.json())
    assert any(len(group["paragraph_ids"]) > 1 for group in groups.json())
    assert first.json()["generated_count"] == 0
    assert first.json()["cached_count"] == len(groups.json())
    assert all(group["analysis_text"].startswith("深度解读：") for group in first.json()["groups"])


def test_translation_and_analysis_use_bounded_concurrency(tmp_path) -> None:
    provider = ConcurrencyTrackingProvider()
    client = build_client(tmp_path, ai_provider=provider)

    imported = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", make_pdf(), "application/pdf")},
    )

    assert imported.status_code == 201
    assert imported.json()["status"] == "ready"
    assert 1 < provider.max_translation_active <= 3
    assert 1 < provider.max_analysis_active <= 3


def test_vocabulary_is_only_created_by_explicit_request_and_persists_context(tmp_path) -> None:
    client = build_client(tmp_path, ai_provider=FakeAIProvider())
    imported = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", make_pdf(), "application/pdf")},
    ).json()
    detail = client.get(f"/api/papers/{imported['id']}").json()

    assert client.get(f"/api/papers/{imported['id']}/vocabulary").json() == []
    paragraph = detail["paragraphs"][-1]
    created = client.post(
        f"/api/papers/{imported['id']}/vocabulary",
        json={"selected_text": "workflows", "paragraph_id": paragraph["id"]},
    )

    assert created.status_code == 201
    item = created.json()
    assert item["normalized_text"] == "workflow"
    assert item["source_sentence"] == paragraph["source_text"]
    assert item["page_number"] == 1
    assert item["contextual_translation"].startswith("译文：")

    duplicate = client.post(
        f"/api/papers/{imported['id']}/vocabulary",
        json={"selected_text": "workflow", "paragraph_id": paragraph["id"]},
    )
    assert duplicate.json()["id"] == item["id"]

    updated = client.patch(
        f"/api/vocabulary/{item['id']}",
        json={"mastery_status": "learning", "note": "重点方法词"},
    )
    assert updated.json()["mastery_status"] == "learning"
    assert client.delete(f"/api/vocabulary/{item['id']}").status_code == 204


def test_chat_automatically_builds_context_persists_history_and_citations(tmp_path) -> None:
    client = build_client(tmp_path, ai_provider=FakeAIProvider())
    imported = client.post(
        "/api/papers/import",
        files={"file": ("paper.pdf", make_pdf(), "application/pdf")},
    ).json()
    detail = client.get(f"/api/papers/{imported['id']}").json()
    paragraph = detail["paragraphs"][-1]

    first = client.post(
        f"/api/papers/{imported['id']}/chat",
        json={
            "question": "作者为什么提出这个工作流？",
            "selected_text": "structured workflow",
            "paragraph_id": paragraph["id"],
        },
    )
    follow_up = client.post(
        f"/api/papers/{imported['id']}/chat",
        json={"question": "它的主要输入是什么？"},
    )
    conversation = client.get(
        f"/api/papers/{imported['id']}/conversation"
    ).json()

    assert first.status_code == 200
    assert first.json()["answer"]["citations"]
    assert first.json()["answer"]["citations"][0]["page_number"] == 1
    assert follow_up.status_code == 200
    assert len(conversation["messages"]) == 4
    assert conversation["messages"][0]["selected_text"] == "structured workflow"


def test_background_import_and_reading_progress_are_recoverable(tmp_path) -> None:
    client = build_client(tmp_path, ai_provider=FakeAIProvider())

    imported = client.post(
        "/api/papers/import?background=true",
        files={"file": ("paper.pdf", make_pdf(), "application/pdf")},
    )
    paper_id = imported.json()["id"]
    detail = client.get(f"/api/papers/{paper_id}").json()

    assert imported.status_code == 201
    assert detail["status"] == "ready"
    assert all(paragraph["translated_text"] for paragraph in detail["paragraphs"])
    groups = client.get(f"/api/papers/{paper_id}/groups").json()
    assert groups and all(group["analysis_text"] for group in groups)
    paragraph_id = detail["paragraphs"][-1]["id"]
    updated = client.patch(
        f"/api/papers/{paper_id}/progress",
        json={"read_progress": 0.64, "last_read_position": paragraph_id},
    )
    reopened = client.get(f"/api/papers/{paper_id}").json()

    assert updated.status_code == 200
    assert reopened["read_progress"] == 0.64
    assert reopened["last_read_position"] == paragraph_id
