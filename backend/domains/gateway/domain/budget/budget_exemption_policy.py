"""平台配额豁免策略（纯函数，不依赖 ORM/IO）。

个人工作区（personal team）下注册的 ``gateway_models`` 属于成员自有资源（BYOK），
其调用不消耗团队共享额度，整段跳过平台配额（成员总量、成员+模型、成员+凭据+模型）。
"""

from __future__ import annotations

import uuid


def is_personal_team_gateway_model(
    record: object,
    *,
    personal_team_id: uuid.UUID | None,
) -> bool:
    """``record`` 是否为该用户个人工作区的模型行。

    系统模型（``SystemGatewayModel`` 无 ``tenant_id``）始终视为非个人，受平台配额约束。
    """
    if personal_team_id is None:
        return False
    tenant_id = getattr(record, "tenant_id", None)
    return isinstance(tenant_id, uuid.UUID) and tenant_id == personal_team_id


def should_skip_platform_budget_preflight(
    record_tenant_id: uuid.UUID | None,
    *,
    billing_team_id: uuid.UUID,
    personal_team_id: uuid.UUID | None,
) -> bool:
    """命中个人工作区模型时跳过全部平台配额（Phase1 + Phase2 自然为空）。

    ``record_tenant_id`` 为解析行的 tenant（应用层从 ``ResolvedModelName.record`` 取出），
    只可能为：计费团队、用户个人团队、或 ``None``（系统模型）。
    因此非空且不等于计费团队时，必为个人工作区模型（共享 vkey 调个人别名），
    可免去个人团队查询直接豁免；等于计费团队时再用 ``personal_team_id`` 判定该团队是否为个人工作区。
    """
    if record_tenant_id is None:
        return False
    if record_tenant_id != billing_team_id:
        return True
    return personal_team_id is not None and record_tenant_id == personal_team_id


__all__ = [
    "is_personal_team_gateway_model",
    "should_skip_platform_budget_preflight",
]
