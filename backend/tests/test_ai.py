from types import SimpleNamespace

from app.ai import QwenProvider
from app.config import Settings


class RecordingCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="测试结果"))]
        )


class RecordingClient:
    def __init__(self) -> None:
        self.completions = RecordingCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


def test_automatic_analysis_disables_thinking() -> None:
    provider = QwenProvider(Settings(dashscope_api_key="test-key"))
    client = RecordingClient()
    provider._client = client

    assert provider.analyze("source") == "测试结果"

    call = client.completions.calls[0]
    assert call["model"] == "qwen3.7-max"
    assert call["extra_body"] == {"enable_thinking": False}


def test_translation_uses_flash_translation_options() -> None:
    provider = QwenProvider(
        Settings(
            dashscope_api_key="test-key",
            qwen_translation_model="qwen-mt-flash",
        )
    )
    client = RecordingClient()
    provider._client = client

    assert provider.translate("source") == "测试结果"

    call = client.completions.calls[0]
    assert call["model"] == "qwen-mt-flash"
    options = call["extra_body"]["translation_options"]
    assert options["source_lang"] == "English"
    assert options["target_lang"] == "Chinese"
