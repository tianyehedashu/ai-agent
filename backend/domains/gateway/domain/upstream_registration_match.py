"""上游模型 ID 与已注册 Gateway 模型 ``real_model`` 的匹配（纯函数，无 I/O）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.domain.litellm_model_id import build_litellm_model_id

if TYPE_CHECKING:
    from collections.abc import Iterable


def upstream_lookup_keys(provider: str, upstream_id: str) -> frozenset[str]:
    """上游列举 id 可能对应的查找键（小写）。"""
    uid = upstream_id.strip()
    if not uid:
        return frozenset()
    built = build_litellm_model_id(provider, uid)
    return frozenset({uid.lower(), built.lower()})


def real_model_lookup_keys(real_model: str) -> frozenset[str]:
    """库内 ``real_model`` 对应的查找键（小写）。"""
    rm = real_model.strip().lower()
    if not rm:
        return frozenset()
    keys = {rm}
    if "/" in rm:
        keys.add(rm.split("/", 1)[1])
    return frozenset(keys)


def match_registered_names(
    provider: str,
    upstream_id: str,
    registered_rows: Iterable[tuple[str, str]],
) -> tuple[str, ...]:
    """返回与上游 id 匹配的已注册别名（``GatewayModel.name``），无则空元组。"""
    up_keys = upstream_lookup_keys(provider, upstream_id)
    if not up_keys:
        return ()
    matched: set[str] = set()
    for name, real_model in registered_rows:
        if up_keys & real_model_lookup_keys(real_model):
            matched.add(name)
    return tuple(sorted(matched))


def format_already_registered_reason(names: tuple[str, ...]) -> str:
    if not names:
        return "该上游模型已在本凭据下注册"
    if len(names) == 1:
        return f"已注册为「{names[0]}」"
    shown = "、".join(names[:3])
    if len(names) > 3:
        shown = f"{shown} 等 {len(names)} 条"
    return f"已注册（{shown}）"


__all__ = [
    "format_already_registered_reason",
    "match_registered_names",
    "real_model_lookup_keys",
    "upstream_lookup_keys",
]
