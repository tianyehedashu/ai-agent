"""
Gateway Domain Errors - 领域错误
"""

from __future__ import annotations

from contextlib import suppress
import uuid

from domains.tenancy.domain.errors import (
    PersonalTeamNotInitializedError,
    TeamNotFoundError,
    TeamPermissionDeniedError,
)
from libs.exceptions.base import HttpMappableDomainError


class GatewayError(HttpMappableDomainError):
    """Gateway 通用异常"""


class NoPersonalTeamForProxyError(GatewayError):
    """API Key 代理入口缺少可用团队（通常为 personal team 未建）"""

    def __init__(self) -> None:
        super().__init__("No team available for this user (personal team missing)")


class GatewayTeamHeaderInvalidError(GatewayError):
    """Gateway 代理入口的 X-Team-Id 不是合法 UUID。"""

    def __init__(self, value: str) -> None:
        super().__init__(f"Invalid X-Team-Id: {value}")
        self.value = value


class GatewayTeamHeaderRequiredError(GatewayError):
    """一把平台 API Key 有多条非 personal 授权时必须显式选择团队。"""

    def __init__(self) -> None:
        super().__init__("X-Team-Id is required for this API key")


class GatewayVkeyTeamHeaderMismatchError(GatewayError):
    """sk-gw-* 请求携带的 X-Team-Id 不在 vkey 主属或已授权 team 集合内。"""

    def __init__(self) -> None:
        super().__init__(
            "X-Team-Id must be vkey's bound team or a granted team"
        )


class VkeyTeamPrefixUnknownError(GatewayError):
    """``<slug>/<model>`` 前缀中的 slug 不在 vkey 已授权 team 集合内（strict 模式）。"""

    def __init__(self, slug: str, available: list[str]) -> None:
        available_str = ", ".join(sorted(available)) if available else "<none>"
        super().__init__(
            f"Team prefix '{slug}' not in vkey grants "
            f"(available: {available_str})"
        )
        self.slug = slug
        self.available = available


class VkeyAmbiguousModelError(GatewayError):
    """无前缀调用时 model 名在多个 grant team 均存在（strict 模式拒绝）。"""

    def __init__(self, model_name: str, team_count: int) -> None:
        super().__init__(
            f"Model '{model_name}' exists in {team_count} granted teams; "
            "use '<team-slug>/<model>' prefix to disambiguate"
        )
        self.model_name = model_name
        self.team_count = team_count


class VkeyGrantTargetNotMemberError(GatewayError):
    """Grant 目标 team 不在 actor 当前 membership 内。"""

    def __init__(self, tenant_ids: list[uuid.UUID]) -> None:
        ids_str = ", ".join(str(t) for t in tenant_ids)
        super().__init__(f"Target team(s) not in your membership: {ids_str}")
        self.tenant_ids = tenant_ids


class ApiKeyGatewayGrantRequiredError(GatewayError):
    """平台 API Key 缺少 Gateway 团队授权。"""

    def __init__(self) -> None:
        super().__init__("API key is not granted to any Gateway team")


class ApiKeyGatewayGrantDeniedError(GatewayError):
    """平台 API Key 未被授权访问指定 Gateway 团队。"""

    def __init__(self, team_id: str) -> None:
        super().__init__(f"API key is not granted to Gateway team: {team_id}")
        self.team_id = team_id


class PlatformApiKeyInvalidError(GatewayError):
    """平台 ``sk-*`` 校验失败（格式/哈希/已撤销/已过期）。"""

    def __init__(self) -> None:
        super().__init__("Invalid API key")


class PlatformApiKeyMissingGatewayProxyScopeError(GatewayError):
    """平台 API Key 缺少 ``gateway:proxy`` 作用域。"""

    def __init__(self) -> None:
        super().__init__("API key missing scope: gateway:proxy")


class InvalidSystemVisibilityError(GatewayError):
    """系统凭据/模型 visibility 或 grant subject/target 枚举非法。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)


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


class SystemVirtualKeyForbiddenError(GatewayError):
    """禁止访问/操作系统内部桥接 Key"""

    def __init__(self, key_id: str) -> None:
        super().__init__(f"系统虚拟 Key 不可访问: {key_id}")


# 向后兼容别名（batch revoke reason、历史测试/import）
SystemVirtualKeyRevokeForbiddenError = SystemVirtualKeyForbiddenError


class VirtualKeyInvalidError(GatewayError):
    """虚拟 Key 无效（撤销/过期/格式错误）"""

    def __init__(self, message: str = "虚拟 Key 无效") -> None:
        super().__init__(message)


class VirtualKeyDecryptError(GatewayError):
    """虚拟 Key 明文解密失败（密钥轮转 / 数据损坏）"""

    def __init__(self) -> None:
        super().__init__("虚拟 Key 明文解密失败")


class CredentialNotFoundError(GatewayError):
    """凭据不存在"""

    def __init__(self, credential_id: str | None = None) -> None:
        msg = "凭据不存在"
        if credential_id:
            msg = f"凭据不存在: {credential_id}"
        super().__init__(msg)


class CredentialApiKeyDecryptError(GatewayError):
    """已存密文无法解密（配置或历史数据问题），需通过轮换新密钥恢复"""

    def __init__(self) -> None:
        super().__init__(
            "无法解密已存储的 API Key，请通过「新 API Key」轮换并保存",
        )


class SystemCredentialAdminRequiredError(GatewayError):
    """管理系统级凭据（scope=system）需要平台管理员身份"""

    def __init__(self) -> None:
        super().__init__("管理系统凭据需要平台管理员身份")


class CredentialNameConflictError(GatewayError):
    """同一用户下同 provider 凭据名称冲突"""

    def __init__(self, provider: str, name: str) -> None:
        super().__init__(f"凭据名称已存在: {provider}/{name}")
        self.provider = provider
        self.name = name


class ModelNotAllowedError(GatewayError):
    """模型不在白名单"""

    def __init__(self, model: str) -> None:
        super().__init__(f"模型不在白名单: {model}")
        self.model = model


class GatewayModelNotFoundError(GatewayError):
    """客户端请求的 model 未在 Gateway 注册（无 GatewayModel / GatewayRoute）。"""

    def __init__(self, model: str, *, team_label: str | None = None) -> None:
        if team_label:
            message = f"未找到已注册的 Gateway 模型: {model}（当前调用团队: {team_label}）"
        else:
            message = f"未找到已注册的 Gateway 模型: {model}"
        super().__init__(message)
        self.model = model
        self.team_label = team_label


class InvocationPolicyViolationError(GatewayError):
    """出站调用策略违规（思考模式 / 温度等）。"""


class CapabilityNotAllowedError(GatewayError):
    """能力不在白名单，或模型主调用面与当前 HTTP 入口不匹配"""

    def __init__(self, capability: str, *, message: str | None = None) -> None:
        super().__init__(message or f"能力不在白名单: {capability}")
        self.capability = capability


class QuotaExhaustedError(GatewayError):
    """配额耗尽统一基类。

    涵盖 platform 预算、upstream 厂商套餐、downstream 客户权益三层配额。
    子类保留独立构造签名以便调用方按场景传参，内部统一映射到基类字段。
    """

    def __init__(
        self,
        *,
        layer: str,
        scope: str,
        quota_label: str,
        reason: str,
        limit: float,
        used: float,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(
            f"[{layer}] {scope}/{quota_label} 配额已耗尽 (reason={reason}): "
            f"限额 {limit}, 已用 {used}"
        )
        self.layer = layer
        self.scope = scope
        self.quota_label = quota_label
        self.reason = reason
        self.limit = limit
        self.used = used
        self.retry_after = retry_after


class BudgetExceededError(QuotaExhaustedError):
    """平台预算（platform 层）超限。"""

    def __init__(self, scope: str, period: str, limit: float, used: float) -> None:
        super().__init__(
            layer="platform",
            scope=scope,
            quota_label=period,
            reason="usd",
            limit=limit,
            used=used,
        )

    @property
    def period(self) -> str:
        """向后兼容：period 即 quota_label。"""
        return self.quota_label


class EntitlementPlanExhaustedError(QuotaExhaustedError):
    """下游客户套餐 (EntitlementPlan) 滚动桶耗尽。

    发生于客户向网关调用前的入站校验阶段。语义为"客户已购额度用完"，
    **不**可经 fallback 突破；HTTP 429 + 业务码 ``gateway/entitlement_exhausted``。
    """

    def __init__(
        self,
        *,
        plan_id: str,
        quota_label: str,
        reason: str,
        retry_at: str | None = None,
    ) -> None:
        retry_after = None
        if retry_at:
            from datetime import UTC, datetime

            with suppress(Exception):
                dt = datetime.fromisoformat(retry_at)
                retry_after = max(0, int((dt - datetime.now(UTC)).total_seconds()))
        super().__init__(
            layer="downstream",
            scope=plan_id,
            quota_label=quota_label,
            reason=reason,
            limit=0.0,
            used=0.0,
            retry_after=retry_after,
        )

    @property
    def plan_id(self) -> str:
        """向后兼容：plan_id 即 scope。"""
        return self.scope


class ProviderPlanExhaustedError(QuotaExhaustedError):
    """上游厂商套餐 (ProviderPlan) 滚动桶耗尽。

    发生于 LiteLLM Router 选中 deployment 后的 pre-call 钩子；Router 会
    cooldown 该 deployment，自动 fallback；调用方一般不直接看到此错误。
    """

    def __init__(
        self,
        *,
        plan_id: str,
        quota_label: str,
        reason: str,
        cooldown_seconds: int,
    ) -> None:
        super().__init__(
            layer="upstream",
            scope=plan_id,
            quota_label=quota_label,
            reason=reason,
            limit=0.0,
            used=0.0,
            retry_after=cooldown_seconds,
        )

    @property
    def plan_id(self) -> str:
        """向后兼容：plan_id 即 scope。"""
        return self.scope

    @property
    def cooldown_seconds(self) -> int:
        """向后兼容：cooldown_seconds 即 retry_after。"""
        return self.retry_after or 0


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
    "ApiKeyGatewayGrantDeniedError",
    "ApiKeyGatewayGrantRequiredError",
    "BudgetExceededError",
    "CapabilityNotAllowedError",
    "CredentialApiKeyDecryptError",
    "CredentialNameConflictError",
    "CredentialNotFoundError",
    "EntitlementPlanExhaustedError",
    "GatewayError",
    "GatewayModelNotFoundError",
    "GatewayTeamHeaderInvalidError",
    "GatewayTeamHeaderRequiredError",
    "GatewayVkeyTeamHeaderMismatchError",
    "GuardrailBlockedError",
    "HttpMappableDomainError",
    "InvocationPolicyViolationError",
    "ManagementEntityNotFoundError",
    "ModelNotAllowedError",
    "NoPersonalTeamForProxyError",
    "PersonalTeamNotInitializedError",
    "PlatformApiKeyInvalidError",
    "PlatformApiKeyMissingGatewayProxyScopeError",
    "ProviderPlanExhaustedError",
    "QuotaExhaustedError",
    "RateLimitExceededError",
    "RouteNotFoundError",
    "SystemCredentialAdminRequiredError",
    "SystemVirtualKeyForbiddenError",
    "SystemVirtualKeyRevokeForbiddenError",
    "TeamNotFoundError",
    "TeamPermissionDeniedError",
    "VirtualKeyDecryptError",
    "VirtualKeyInvalidError",
    "VirtualKeyNotFoundError",
    "VkeyAmbiguousModelError",
    "VkeyGrantTargetNotMemberError",
    "VkeyTeamPrefixUnknownError",
]
