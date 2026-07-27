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

    def answer(
        self,
        question: str,
        context: str,
        history: list[dict[str, str]],
    ) -> str:
        """Answer a paper-grounded question with conversational history."""


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
        if self.settings.qwen_translation_model.startswith("qwen-mt-"):
            response = self._require_client().chat.completions.create(
                model=self.settings.qwen_translation_model,
                messages=[{"role": "user", "content": text}],
                extra_body={
                    "translation_options": {
                        "source_lang": "English",
                        "target_lang": "Chinese",
                        "domains": (
                            "The text is from an academic research paper. Preserve formulas, "
                            "variables, citation numbers, figure and table references, and "
                            "translate technical terminology consistently in a rigorous style."
                        ),
                    }
                },
            )
        else:
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

    def answer(
        self,
        question: str,
        context: str,
        history: list[dict[str, str]],
    ) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是论文研读问答助手。优先依据给定论文上下文回答，并区分论文证据、"
                    "基于文本的推断和补充背景。找不到依据时直接说明，不得伪造引用。"
                    "回答清楚、具体，必要时解释公式、方法或论证关系。"
                ),
            },
            *history[-10:],
            {
                "role": "user",
                "content": f"论文上下文：\n{context}\n\n问题：{question}",
            },
        ]
        response = self._require_client().chat.completions.create(
            model=self.settings.qwen_chat_model,
            temperature=0.25,
            messages=messages,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Qwen 没有返回回答")
        return content.strip()
