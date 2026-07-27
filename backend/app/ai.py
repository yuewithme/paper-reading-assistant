from typing import Protocol

from openai import OpenAI

from .config import Settings


class AIConfigurationError(RuntimeError):
    pass


class AIProvider(Protocol):
    def translate(self, text: str) -> str:
        """Translate one academic paragraph into Chinese."""

    def analyze(self, text: str) -> str:
        """Explain one semantic group deeply in Chinese."""


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

    def analyze(self, text: str) -> str:
        response = self._require_client().chat.completions.create(
            model=self.settings.qwen_analysis_model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是英文论文深度研读助手。用中文解释给定语义块为什么出现在这里、"
                        "它在论证中的作用、关键概念或方法，以及必要的局限。不要重复逐句翻译。"
                        "明确区分“论文明确表达”“基于文本的推断”“补充背景”。"
                        "内容简单时简洁，关键内容可以深入；不要套用固定栏目。"
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Qwen 没有返回解读")
        return content.strip()
