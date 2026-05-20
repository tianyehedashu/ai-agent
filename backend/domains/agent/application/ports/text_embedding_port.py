"""文本嵌入应用端口（Agent 记忆 / RAG）。"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class TextEmbeddingPort(Protocol):
    async def embed(self, text: str) -> list[float]: ...
