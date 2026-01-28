"""
Exceptions - 自定义异常类

提供统一的异常层次结构，便于错误处理和 API 响应。
"""

from typing import Any


class AIAgentError(Exception):
    """AI Agent 基础异常

    所有自定义异常的基类。

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


class ValidationError(AIAgentError):
    """验证错误

    当输入数据验证失败时抛出。
    """

    def __init__(
        self,
        message: str = "Validation failed",
        code: str = "VALIDATION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code, details)


class NotFoundError(AIAgentError):
    """资源不存在

    当请求的资源不存在时抛出。
    """

    def __init__(
        self,
        resource: str,
        resource_id: str | None = None,
        code: str = "NOT_FOUND",
    ) -> None:
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} not found: {resource_id}"
        super().__init__(message, code, {"resource": resource, "id": resource_id})
        self.resource = resource
        self.resource_id = resource_id


class PermissionDeniedError(AIAgentError):
    """权限不足

    当用户没有权限执行操作时抛出。
    """

    def __init__(
        self,
        message: str = "Permission denied",
        code: str = "PERMISSION_DENIED",
        action: str | None = None,
        resource: str | None = None,
    ) -> None:
        details = {}
        if action:
            details["action"] = action
        if resource:
            details["resource"] = resource
        super().__init__(message, code, details)


class AuthenticationError(AIAgentError):
    """认证错误

    当认证失败时抛出。
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        code: str = "AUTHENTICATION_ERROR",
    ) -> None:
        super().__init__(message, code)


class TokenError(AuthenticationError):
    """Token 错误

    当 Token 无效或过期时抛出。
    """

    def __init__(
        self,
        message: str = "Invalid token",
        code: str = "TOKEN_ERROR",
        expired: bool = False,
    ) -> None:
        super().__init__(message, code)
        self.expired = expired


class ConflictError(AIAgentError):
    """资源冲突

    当操作导致资源冲突时抛出（如重复创建）。
    """

    def __init__(
        self,
        message: str = "Resource conflict",
        code: str = "CONFLICT",
        resource: str | None = None,
    ) -> None:
        details = {"resource": resource} if resource else {}
        super().__init__(message, code, details)


class RateLimitError(AIAgentError):
    """速率限制

    当请求超过速率限制时抛出。
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        code: str = "RATE_LIMIT",
        retry_after: int | None = None,
    ) -> None:
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, code, details)
        self.retry_after = retry_after


class ExternalServiceError(AIAgentError):
    """外部服务错误

    当调用外部服务（LLM、向量数据库等）失败时抛出。
    """

    def __init__(
        self,
        service: str,
        message: str | None = None,
        code: str = "EXTERNAL_SERVICE_ERROR",
        original_error: Exception | None = None,
    ) -> None:
        msg = message or f"External service error: {service}"
        super().__init__(msg, code, {"service": service})
        self.service = service
        self.original_error = original_error


class ToolExecutionError(AIAgentError):
    """工具执行错误

    当 Agent 工具执行失败时抛出。
    """

    def __init__(
        self,
        tool_name: str,
        message: str | None = None,
        code: str = "TOOL_EXECUTION_ERROR",
        original_error: Exception | None = None,
    ) -> None:
        msg = message or f"Tool execution failed: {tool_name}"
        super().__init__(msg, code, {"tool": tool_name})
        self.tool_name = tool_name
        self.original_error = original_error


class CheckpointError(AIAgentError):
    """检查点错误

    当检查点操作失败时抛出。
    """

    def __init__(
        self,
        message: str = "Checkpoint operation failed",
        code: str = "CHECKPOINT_ERROR",
        checkpoint_id: str | None = None,
    ) -> None:
        details = {"checkpoint_id": checkpoint_id} if checkpoint_id else {}
        super().__init__(message, code, details)
