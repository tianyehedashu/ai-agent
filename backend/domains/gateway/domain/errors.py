"""
Gateway Domain Errors - 领域错误
"""

from __future__ import annotations

from exceptions import AIAgentError


class GatewayError(AIAgentError):
    """Gateway 通用异常"""


class TeamNotFoundError(GatewayError):
    """团队不存在"""

    def __init__(self, team_id: str) -> None:
        super().__init__(f"团队不存在: {team_id}")
        self.team_id = team_id


class TeamPermissionDeniedError(GatewayError):
    """团队权限不足"""

    def __init__(self, team_id: str, required_role: str | None = None) -> None:
        msg = f"团队 {team_id} 权限不足"
        if required_role:
            msg += f"，需要角色: {required_role}"
        super().__init__(msg)
        self.team_id = team_id


class PersonalTeamNotInitializedError(GatewayError):
    """用户 personal team 未初始化（管理面）"""

    def __init__(self) -> None:
        super().__init__("Personal team not initialized; please contact admin")


class NoPersonalTeamForProxyError(GatewayError):
    """API Key 代理入口缺少可用团队（通常为 personal team 未建）"""

    def __init__(self) -> None:
        super().__init__("No team available for this user (personal team missing)")


class ManagementEntityNotFoundError(GatewayError):
    """管理面资源不存在（模型/路由/告警规则等）"""

    def __init__(self, kind: str, entity_id: str) -> None:
        super().__init__(f"{kind} not found: {entity_id}")
        self.kind = kind
        self.entity_id = entity_id


class VirtualKeyNotFoundError(GatewayError):
    """虚拟 Key 不存在"""

    def __init__(self, key_id: str) -> None:
        super().__init__(f"虚拟 Key 不存在: {key_id}")


class VirtualKeyInvalidError(GatewayError):
    """虚拟 Key 无效（撤销/过期/格式错误）"""

    def __init__(self, message: str = "虚拟 Key 无效") -> None:
        super().__init__(message)


class CredentialNotFoundError(GatewayError):
    """凭据不存在"""

    def __init__(self, credential_id: str | None = None) -> None:
        msg = "凭据不存在"
        if credential_id:
            msg = f"凭据不存在: {credential_id}"
        super().__init__(msg)


class ModelNotAllowedError(GatewayError):
    """模型不在白名单"""

    def __init__(self, model: str) -> None:
        super().__init__(f"模型不在白名单: {model}")
        self.model = model


class CapabilityNotAllowedError(GatewayError):
    """能力不在白名单"""

    def __init__(self, capability: str) -> None:
        super().__init__(f"能力不在白名单: {capability}")
        self.capability = capability


class BudgetExceededError(GatewayError):
    """预算超限"""

    def __init__(self, scope: str, period: str, limit: float, used: float) -> None:
        super().__init__(
            f"{scope}/{period} 预算已用尽: 限额 {limit}, 已用 {used}"
        )
        self.scope = scope
        self.period = period
        self.limit = limit
        self.used = used


class RateLimitExceededError(GatewayError):
    """限流超限"""

    def __init__(self, scope: str, retry_after: int | None = None) -> None:
        super().__init__(f"{scope} 触发限流")
        self.scope = scope
        self.retry_after = retry_after


class RouteNotFoundError(GatewayError):
    """路由未配置"""

    def __init__(self, virtual_model: str) -> None:
        super().__init__(f"未找到路由: {virtual_model}")
        self.virtual_model = virtual_model


class GuardrailBlockedError(GatewayError):
    """Guardrail 拦截"""


__all__ = [
    "BudgetExceededError",
    "CapabilityNotAllowedError",
    "CredentialNotFoundError",
    "GatewayError",
    "GuardrailBlockedError",
    "ManagementEntityNotFoundError",
    "ModelNotAllowedError",
    "NoPersonalTeamForProxyError",
    "PersonalTeamNotInitializedError",
    "RateLimitExceededError",
    "RouteNotFoundError",
    "TeamNotFoundError",
    "TeamPermissionDeniedError",
    "VirtualKeyInvalidError",
    "VirtualKeyNotFoundError",
]
