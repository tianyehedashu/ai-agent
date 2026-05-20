"""无域依赖的异常基类（打破 libs.exceptions ↔ tenancy.domain.errors 循环导入）。"""

from typing import Any


class AIAgentError(Exception):
    """AI Agent 基础异常

    Attributes:
        message: 错误消息
        code: 错误代码（可选）
        details: 额外详情（可选）
    """

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class HttpMappableDomainError(AIAgentError):
    """可由 Presentation 映射为 HTTP 的领域错误基类。"""


__all__ = ["AIAgentError", "HttpMappableDomainError"]
