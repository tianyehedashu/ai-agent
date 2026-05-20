"""Listing Studio 能力所需模型特性策略（纯函数）。"""

from __future__ import annotations


def merge_model_feature_sources(
    catalog_features: frozenset[str] | None,
    static_features: frozenset[str] | None,
) -> frozenset[str] | None:
    """合并 Gateway 目录特性与静态配置；皆无则 None（无法校验）。"""
    if catalog_features is not None:
        return catalog_features
    if static_features is not None:
        return static_features
    return None


def missing_capability_features(
    required: frozenset[str],
    available: frozenset[str] | None,
) -> frozenset[str]:
    """返回缺失的特性名；无 required 或 available 未知时为空。"""
    if not required or available is None:
        return frozenset()
    return required - available
