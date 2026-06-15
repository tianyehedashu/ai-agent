"""vkey 跨团队 model 前缀派发纯规则（无 IO）。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from domains.gateway.domain.errors import VkeyTeamPrefixUnknownError


@dataclass(frozen=True, slots=True)
class VkeyModelDispatch:
    """前缀派发结果。"""

    effective_team_id: UUID
    real_model_name: str
    matched_slug: str | None


def resolve_vkey_model_prefix(
    *,
    bound_team_id: UUID,
    raw_model: str,
    slug_map: dict[str, UUID],
    strict: bool,
) -> VkeyModelDispatch:
    """根据 model 名前缀决定调用落哪个 team（纯函数）。

    - 无 ``/`` → 主属 team，model 保持原样
    - ``slug/rest`` 且 slug 在 grants → 命中 team，model 为 rest
    - slug 未命中 + strict → ``VkeyTeamPrefixUnknownError``
    - slug 未命中 + 非 strict → 主属 team，model 保持原样（vendor prefix 走主属解析）
    """
    if "/" not in raw_model:
        return VkeyModelDispatch(
            effective_team_id=bound_team_id,
            real_model_name=raw_model,
            matched_slug=None,
        )

    slash_idx = raw_model.index("/")
    slug_candidate = raw_model[:slash_idx]
    rest = raw_model[slash_idx + 1 :]

    matched_tenant_id = slug_map.get(slug_candidate)
    if matched_tenant_id is not None:
        return VkeyModelDispatch(
            effective_team_id=matched_tenant_id,
            real_model_name=rest,
            matched_slug=slug_candidate,
        )

    if strict:
        raise VkeyTeamPrefixUnknownError(slug_candidate, list(slug_map.keys()))

    return VkeyModelDispatch(
        effective_team_id=bound_team_id,
        real_model_name=raw_model,
        matched_slug=None,
    )


def resolve_vkey_proxy_list_id(
    *,
    bound_team_id: UUID,
    model_tenant_id: UUID,
    model_name: str,
    slug_by_tenant: dict[UUID, str],
) -> str:
    """代理端 GET /v1/models 列表 id（与 dispatch 前缀规则对称）。

    - 主属 team → 裸注册名
    - grant team → ``{slug}/{model_name}``
    """
    if model_tenant_id == bound_team_id:
        return model_name
    slug = slug_by_tenant.get(model_tenant_id)
    if slug is None:
        msg = f"missing team slug for tenant_id={model_tenant_id}"
        raise KeyError(msg)
    return f"{slug}/{model_name}"


__all__ = [
    "VkeyModelDispatch",
    "resolve_vkey_model_prefix",
    "resolve_vkey_proxy_list_id",
]
