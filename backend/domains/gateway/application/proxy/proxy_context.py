"""单次 /v1 代理调用的共享上下文类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid

from domains.gateway.domain.proxy.proxy_policy import BudgetReservation
from domains.gateway.domain.quota.period_reset_anchor import PeriodResetAnchor
from domains.gateway.domain.quota.quota_plan import PlanQuotaSpec, QuotaPlanReservation
from domains.gateway.domain.types import GatewayCapability, GatewayInboundVia, VirtualKeyPrincipal

from .proxy_timing import GatewayProxyTiming

BudgetAnchorCoord = tuple[
    str, uuid.UUID | None, str, str | None, uuid.UUID | None, uuid.UUID | None
]


@dataclass
class PlatformBudgetPreflightState:
    """preflight 时刻锁定的平台预算周期锚点（reserve / commit 共用同一窗口）。"""

    anchor_pins: dict[BudgetAnchorCoord, PeriodResetAnchor] = field(default_factory=dict)
    reservations: list[BudgetReservation] = field(default_factory=list)
    token_reservations_released: bool = False


@dataclass
class EntitlementReservationState:
    """单次调用命中的下游 entitlement 套餐预扣信息，跨 reserve / settle 阶段共享。"""

    plan_id: uuid.UUID
    plan_label: str | None
    specs: list[PlanQuotaSpec]
    reservations: list[QuotaPlanReservation]


@dataclass
class ProxyContext:
    """单次 OpenAI 兼容代理调用的上下文。

    Attributes:
        team_id: **计费团队**（BillingTeam，与日志 ``gateway_team_id``、
            ``gateway_request_logs.team_id`` 一致），为一次调用归属的租户键。
        user_id: 触发用户（可为 None，视入口而定）。
        vkey: 虚拟 Key 主体；内部 system vkey 走同字段；平台 ``sk-*`` 入站时可为 None。
        capability: 网关能力枚举。
        request_id: 关联 ID。
        store_full_messages / guardrail_enabled: 日志与护栏策略。
        budget_model: 请求体中的 ``model`` 字符串（与 ``gateway_budgets.model_name`` 对齐），
            用于模型级预算；未设置时仅校验/结算「全模型」汇总行（``model_name IS NULL``）。
        inbound_via: 入站鉴权路径 ``vkey``（``sk-gw-*``）或 ``apikey``（平台 ``sk-*`` + ``gateway:proxy``）。
        platform_api_key_id: 当 ``inbound_via=apikey`` 时为 Identity API Key 主键；否则为 ``None``。
        platform_api_key_grant_id: 当 ``inbound_via=apikey`` 时为命中的 Gateway grant 主键。

    与 ``BudgetUpsert.scope``（system/team/key/user）及 HTTP ``usage_aggregation`` 正交。
    """

    team_id: uuid.UUID
    user_id: uuid.UUID | None
    vkey: VirtualKeyPrincipal | None
    capability: GatewayCapability
    request_id: str
    store_full_messages: bool
    guardrail_enabled: bool
    budget_model: str | None = None
    inbound_via: GatewayInboundVia = "vkey"
    platform_api_key_id: uuid.UUID | None = None
    platform_api_key_grant_id: uuid.UUID | None = None
    allowed_models: tuple[str, ...] = ()
    allowed_capabilities: tuple[GatewayCapability, ...] = ()
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    entitlement_state: EntitlementReservationState | None = None
    platform_budget_preflight: PlatformBudgetPreflightState | None = None
    client_ua: str | None = None
    client_type: str = "unknown"
    user_display_snapshot: str | None = None
    """调用者展示名（name 或 email）；在鉴权/桥接层解析一次，metadata 构建不再查库。"""
    proxy_timing: GatewayProxyTiming | None = None
    """``chat_completion`` 写入的网关内耗时，供 OpenAI 兼容面响应头透出。"""
    personal_team_id: uuid.UUID | None = None
    """触发用户个人工作区 team id（请求级懒加载缓存，用于平台配额豁免判定）。"""
    # ─── 跨团队派发（multi-tenant vkey）────────────────────────────────────
    client_raw_model: str | None = None
    """派发前的原始 model 名（含 ``<slug>/`` 前缀，若有）；写到日志 ``gateway_route_name``。"""
    dispatched_via_prefix: bool = False
    """本次调用是否通过 ``<team-slug>/<model>`` 前缀派发（写到日志 ``gateway_dispatched_via_prefix``）。"""


__all__ = [
    "BudgetAnchorCoord",
    "EntitlementReservationState",
    "PlatformBudgetPreflightState",
    "ProxyContext",
]
