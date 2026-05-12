"""
Gateway Domain Types - 领域类型定义

包含枚举、值对象与领域 DTO。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
import uuid


# =============================================================================
# 枚举
# =============================================================================


class TeamKind(str, Enum):
    """团队类型"""

    PERSONAL = "personal"  # 个人团队（用户注册时自动创建）
    SHARED = "shared"  # 共享团队


class TeamRole(str, Enum):
    """团队成员角色"""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class CredentialScope(str, Enum):
    """凭据作用域"""

    SYSTEM = "system"  # 全局系统凭据
    TEAM = "team"  # 团队凭据
    USER = "user"  # 用户个人凭据


class BudgetScope(str, Enum):
    """预算作用域"""

    SYSTEM = "system"
    TEAM = "team"
    KEY = "key"  # 单个虚拟 Key
    USER = "user"


class BudgetPeriod(str, Enum):
    """预算周期"""

    DAILY = "daily"
    MONTHLY = "monthly"
    TOTAL = "total"  # 累计（不重置）


class GatewayCapability(str, Enum):
    """Gateway 调用能力（与 OpenAI 兼容入口对应）"""

    CHAT = "chat"
    EMBEDDING = "embedding"
    IMAGE = "image"
    AUDIO_TRANSCRIPTION = "audio_transcription"
    AUDIO_SPEECH = "audio_speech"
    RERANK = "rerank"


class RoutingStrategy(str, Enum):
    """路由策略（对齐 LiteLLM Router）"""

    SIMPLE_SHUFFLE = "simple-shuffle"
    LEAST_BUSY = "least-busy"
    LATENCY_BASED = "latency-based-routing"
    USAGE_BASED = "usage-based-routing-v2"
    COST_BASED = "cost-based-routing"


class FallbackKind(str, Enum):
    """Fallback 类型"""

    GENERAL = "general"
    CONTENT_POLICY = "content_policy"
    CONTEXT_WINDOW = "context_window"


class RequestStatus(str, Enum):
    """调用状态"""

    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    BUDGET_EXCEEDED = "budget_exceeded"
    GUARDRAIL_BLOCKED = "guardrail_blocked"


class AlertMetric(str, Enum):
    """告警指标"""

    ERROR_RATE = "error_rate"
    BUDGET_USAGE = "budget_usage"
    LATENCY_P95 = "latency_p95"
    REQUEST_RATE = "request_rate"


class AlertChannel(str, Enum):
    """告警通知渠道"""

    WEBHOOK = "webhook"
    INAPP = "inapp"
    EMAIL = "email"


# =============================================================================
# 值对象与 DTO
# =============================================================================


@dataclass(frozen=True)
class TeamContext:
    """团队上下文（请求级，注入 PermissionContext）"""

    team_id: uuid.UUID
    team_role: TeamRole
    team_kind: TeamKind = TeamKind.PERSONAL


@dataclass(frozen=True)
class ManagementTeamContext:
    """管理面 `/api/v1/gateway/*` 解析后的团队上下文（应用层产出，Presentation 消费）"""

    team_id: uuid.UUID
    team_kind: str
    team_role: str
    user_id: uuid.UUID
    is_platform_admin: bool


@dataclass(frozen=True)
class VirtualKeyPrincipal:
    """虚拟 Key 鉴权后的主体信息"""

    vkey_id: uuid.UUID
    vkey_name: str
    team_id: uuid.UUID
    user_id: uuid.UUID | None  # 创建者
    allowed_models: tuple[str, ...]
    allowed_capabilities: tuple[GatewayCapability, ...]
    rpm_limit: int | None
    tpm_limit: int | None
    store_full_messages: bool
    guardrail_enabled: bool
    is_system: bool


@dataclass
class RouteConfig:
    """路由配置（对齐 LiteLLM Router 的 model_list 配置）"""

    virtual_model: str
    primary_models: list[str]
    fallbacks_general: list[str] = field(default_factory=list)
    fallbacks_content_policy: list[str] = field(default_factory=list)
    fallbacks_context_window: list[str] = field(default_factory=list)
    strategy: RoutingStrategy = RoutingStrategy.SIMPLE_SHUFFLE
    retry_policy: dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageRecord:
    """单次调用的用量记录（写日志前的中间表示）"""

    capability: GatewayCapability
    real_model: str
    provider: str
    status: RequestStatus
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    latency_ms: int = 0
    ttfb_ms: int | None = None
    error_code: str | None = None
    cache_hit: bool = False
    fallback_chain: list[str] = field(default_factory=list)


@dataclass
class DashboardSummary:
    """仪表盘汇总"""

    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: Decimal
    success_count: int
    failure_count: int
    avg_latency_ms: float
    p95_latency_ms: float


@dataclass
class TimeSeriesPoint:
    """时序点"""

    bucket: datetime
    requests: int
    tokens: int
    cost_usd: Decimal
    errors: int


__all__ = [
    "AlertChannel",
    "AlertMetric",
    "BudgetPeriod",
    "BudgetScope",
    "CredentialScope",
    "DashboardSummary",
    "FallbackKind",
    "GatewayCapability",
    "ManagementTeamContext",
    "RequestStatus",
    "RouteConfig",
    "RoutingStrategy",
    "TeamContext",
    "TeamKind",
    "TeamRole",
    "TimeSeriesPoint",
    "UsageRecord",
    "VirtualKeyPrincipal",
]
