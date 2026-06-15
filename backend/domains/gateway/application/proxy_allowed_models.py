"""代理入站 allowed_models 白名单解析（presentation 与 application 边界）。"""

from __future__ import annotations


def resolve_proxy_allowed_model_names(
    *,
    vkey_allowed: tuple[str, ...] | None = None,
    grant_allowed: tuple[str, ...] | None = None,
) -> set[str] | None:
    """合并 vkey 与 apikey grant 的模型白名单；空 tuple 表示允许全部。"""
    allowed: set[str] | None = None
    if vkey_allowed:
        allowed = set(vkey_allowed)
    if grant_allowed:
        grant_set = set(grant_allowed)
        allowed = grant_set if allowed is None else allowed & grant_set
    return allowed


__all__ = ["resolve_proxy_allowed_model_names"]
