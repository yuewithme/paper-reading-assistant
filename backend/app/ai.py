from typing import Protocol

from openai import OpenAI

from .config import Settings


class AIConfigurationError(RuntimeError):
    pass


class AIProvider(Protocol):
    def translate(self, text: str) -> str:
        """Translate one academic paragraph into Chinese."""


class QwenProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: OpenAI | None = None
        if settings.llm_configured:
            self._client = OpenAI(
                api_key=settings.dashscope_api_key.get_secret_value(),
                base_url=settings.qwen_base_url,
            )

    def _require_client(self) -> OpenAI:
        if self._client is None:
            raise AIConfigurationError("请先在项目根目录的 .env 中填写 DASHSCOPE_API_KEY")
        return self._client

    def translate(self, text: str) -> str:
        response = self._require_client().chat.completions.create(
            model=self.settings.qwen_translation_model,
            temperature=0.15,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是严谨的学术翻译助手。将英文论文内容翻译为准确、自然的中文。"
                        "不要补充作者没有表达的内容；保留公式、变量、引用编号和图表编号；"
                        "重要术语首次出现时保留英文。只输出译文。"
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Qwen 没有返回译文")
        return content.strip()
