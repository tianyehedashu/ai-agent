"""配额规则聚合查询缓存（管理面读路径，L1 内存 + Redis，版本号失效）。"""

from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING
import uuid

from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.gateway.application.management.quota_rule_read_model import (
        QuotaRuleReadModel,
    )

logger = get_logger(__name__)

_TTL_SEC = 30.0
_LOCAL_MAX = 512
_REDIS_VERSION_KEY_PREFIX = "gw:quota_rules:ver:"
_REDIS_ENTRY_PREFIX = "gw:quota_rules:"

_LocalKey = tuple[str, str]  # (version, cache_key)
_LocalEntry = tuple[list[dict], float]

_LOCAL: dict[_LocalKey, _LocalEntry] = {}


def _filter_hash(filters: object | None) -> str:
    """为过滤条件生成稳定哈希。"""
    if filters is None:
        return "none"
    payload = json.dumps(filters, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _build_cache_key(
    team_id: uuid.UUID,
    *,
    actor_role_hash: str,
    filter_hash: str,
) -> str:
    return f"{team_id}:{actor_role_hash}:{filter_hash}"


def _quota_rule_to_dict(rule: QuotaRuleReadModel) -> dict:
    """将 QuotaRuleReadModel 序列化为可 JSON 的字典。"""
    from decimal import Decimal

    def _ser(value: object) -> object:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    # 手动构建字典，确保所有值可 JSON 序列化
    key = rule.key
    source_ref = rule.source_ref
    limits = rule.limits
    usage = rule.usage

    result: dict[str, object] = {
        "key": {
            "team_id": str(key.team_id),
            "layer": key.layer,
            "user_id": str(key.user_id) if key.user_id else None,
            "credential_id": str(key.credential_id) if key.credential_id else None,
            "model_name": key.model_name,
            "period": key.period,
            "window_seconds": key.window_seconds,
            "reset_strategy": key.reset_strategy,
            "period_timezone": key.period_timezone,
            "period_reset_minutes": key.period_reset_minutes,
            "period_reset_day": key.period_reset_day,
            "access_kind": key.access_kind,
            "access_id": str(key.access_id) if key.access_id else None,
            "quota_label": key.quota_label,
            "target_kind": key.target_kind,
            "target_id": str(key.target_id) if key.target_id else None,
        },
        "source_ref": {
            "layer": source_ref.layer,
            "budget_id": str(source_ref.budget_id) if source_ref.budget_id else None,
            "plan_id": str(source_ref.plan_id) if source_ref.plan_id else None,
            "quota_id": str(source_ref.quota_id) if source_ref.quota_id else None,
        },
        "limits": {
            "limit_usd": str(limits.limit_usd) if limits.limit_usd is not None else None,
            "soft_limit_usd": str(limits.soft_limit_usd)
            if limits.soft_limit_usd is not None
            else None,
            "limit_tokens": limits.limit_tokens,
            "limit_requests": limits.limit_requests,
            "unit_price_usd_per_token": str(limits.unit_price_usd_per_token)
            if limits.unit_price_usd_per_token is not None
            else None,
            "unit_price_usd_per_request": str(limits.unit_price_usd_per_request)
            if limits.unit_price_usd_per_request is not None
            else None,
        },
        "plan_label": rule.plan_label,
        "is_active": rule.is_active,
    }

    if usage is not None:
        result["usage"] = {
            "current_usd": str(usage.current_usd) if usage.current_usd is not None else None,
            "current_tokens": usage.current_tokens,
            "current_requests": usage.current_requests,
            "reset_at": usage.reset_at.isoformat() if usage.reset_at else None,
            "budget_reset_at": usage.budget_reset_at.isoformat() if usage.budget_reset_at else None,
        }
    else:
        result["usage"] = None

    return result


def _dict_to_quota_rule(data: dict) -> QuotaRuleReadModel:
    """从字典反序列化为 QuotaRuleReadModel。"""
    from datetime import datetime
    from decimal import Decimal

    from domains.gateway.application.management.quota_rule_read_model import (
        QuotaRuleKey,
        QuotaRuleLimits,
        QuotaRuleReadModel,
        QuotaRuleSourceRef,
        QuotaRuleUsage,
    )

    key_data = data["key"]
    key = QuotaRuleKey(
        team_id=uuid.UUID(key_data["team_id"]),
        layer=key_data["layer"],
        user_id=uuid.UUID(key_data["user_id"]) if key_data.get("user_id") else None,
        credential_id=uuid.UUID(key_data["credential_id"])
        if key_data.get("credential_id")
        else None,
        model_name=key_data.get("model_name"),
        period=key_data.get("period"),
        window_seconds=key_data.get("window_seconds"),
        reset_strategy=key_data.get("reset_strategy"),
        period_timezone=key_data.get("period_timezone"),
        period_reset_minutes=key_data.get("period_reset_minutes"),
        period_reset_day=key_data.get("period_reset_day"),
        access_kind=key_data["access_kind"],
        access_id=uuid.UUID(key_data["access_id"]) if key_data.get("access_id") else None,
        quota_label=key_data.get("quota_label"),
        target_kind=key_data.get("target_kind"),
        target_id=uuid.UUID(key_data["target_id"]) if key_data.get("target_id") else None,
    )

    src_data = data["source_ref"]
    source_ref = QuotaRuleSourceRef(
        layer=src_data["layer"],
        budget_id=uuid.UUID(src_data["budget_id"]) if src_data.get("budget_id") else None,
        plan_id=uuid.UUID(src_data["plan_id"]) if src_data.get("plan_id") else None,
        quota_id=uuid.UUID(src_data["quota_id"]) if src_data.get("quota_id") else None,
    )

    limits_data = data["limits"]
    limits = QuotaRuleLimits(
        limit_usd=Decimal(limits_data["limit_usd"])
        if limits_data.get("limit_usd") is not None
        else None,
        soft_limit_usd=Decimal(limits_data["soft_limit_usd"])
        if limits_data.get("soft_limit_usd") is not None
        else None,
        limit_tokens=limits_data.get("limit_tokens"),
        limit_requests=limits_data.get("limit_requests"),
        unit_price_usd_per_token=Decimal(limits_data["unit_price_usd_per_token"])
        if limits_data.get("unit_price_usd_per_token") is not None
        else None,
        unit_price_usd_per_request=Decimal(limits_data["unit_price_usd_per_request"])
        if limits_data.get("unit_price_usd_per_request") is not None
        else None,
    )

    usage = None
    usage_data = data.get("usage")
    if usage_data is not None:
        usage = QuotaRuleUsage(
            current_usd=Decimal(usage_data["current_usd"])
            if usage_data.get("current_usd") is not None
            else None,
            current_tokens=usage_data["current_tokens"]
            if usage_data.get("current_tokens") is not None
            else None,
            current_requests=usage_data["current_requests"]
            if usage_data.get("current_requests") is not None
            else None,
            reset_at=datetime.fromisoformat(usage_data["reset_at"])
            if usage_data.get("reset_at")
            else None,
            budget_reset_at=datetime.fromisoformat(usage_data["budget_reset_at"])
            if usage_data.get("budget_reset_at")
            else None,
        )

    return QuotaRuleReadModel(
        key=key,
        source_ref=source_ref,
        limits=limits,
        usage=usage,
        plan_label=data.get("plan_label"),
        is_active=data.get("is_active", True),
    )


# ---------------------------------------------------------------------------
# Local L1 cache helpers
# ---------------------------------------------------------------------------


def _get_local(version: str, cache_key: str) -> list[QuotaRuleReadModel] | None:
    hit = _LOCAL.get((version, cache_key))
    if hit is None:
        return None
    snapshot, ts = hit
    if time.monotonic() - ts >= _TTL_SEC:
        _LOCAL.pop((version, cache_key), None)
        return None
    try:
        return [_dict_to_quota_rule(item) for item in snapshot]
    except Exception:
        logger.warning("Quota rule local cache deserialization failed", exc_info=True)
        _LOCAL.pop((version, cache_key), None)
        return None


def _put_local(version: str, cache_key: str, rules: list[QuotaRuleReadModel]) -> None:
    if len(_LOCAL) >= _LOCAL_MAX:
        oldest = min(_LOCAL.items(), key=lambda item: item[1][1])[0]
        _LOCAL.pop(oldest, None)
    snapshot = [_quota_rule_to_dict(rule) for rule in rules]
    _LOCAL[(version, cache_key)] = (snapshot, time.monotonic())


def clear_local_quota_rule_cache_for_team(team_id: uuid.UUID) -> None:
    """同步清除与指定团队相关的所有本地配额规则缓存（写路径调用）。"""
    prefix = f"{team_id}:"
    keys_to_remove = [k for k in _LOCAL if k[1].startswith(prefix)]
    for k in keys_to_remove:
        _LOCAL.pop(k, None)


def clear_all_local_quota_rule_cache_for_tests() -> None:
    """测试专用：清除全部本地配额规则缓存。"""
    _LOCAL.clear()


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------


async def _get_version(team_id: uuid.UUID) -> str:
    redis = await _get_redis_client()
    if redis is None:
        return "0"
    try:
        raw = await redis.get(f"{_REDIS_VERSION_KEY_PREFIX}{team_id}")
        return raw.decode() if isinstance(raw, bytes) else (raw or "0")
    except Exception:
        logger.warning("Redis quota rule version read failed", exc_info=True)
        return "0"


async def _bump_version(team_id: uuid.UUID) -> None:
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        await redis.incr(f"{_REDIS_VERSION_KEY_PREFIX}{team_id}")
    except Exception:
        logger.warning("Redis quota rule version bump failed", exc_info=True)


async def _get_redis(version: str, cache_key: str) -> list[QuotaRuleReadModel] | None:
    redis = await _get_redis_client()
    if redis is None:
        return None
    try:
        raw = await redis.get(f"{_REDIS_ENTRY_PREFIX}{version}:{cache_key}")
    except Exception:
        logger.warning("Redis quota rule cache read failed", exc_info=True)
        return None
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
        if not isinstance(payload, list):
            return None
        return [_dict_to_quota_rule(item) for item in payload]
    except Exception:
        logger.warning("Redis quota rule cache deserialization failed", exc_info=True)
        return None


async def _put_redis(version: str, cache_key: str, rules: list[QuotaRuleReadModel]) -> None:
    redis = await _get_redis_client()
    if redis is None:
        return
    try:
        snapshot = [_quota_rule_to_dict(rule) for rule in rules]
        await redis.set(
            f"{_REDIS_ENTRY_PREFIX}{version}:{cache_key}",
            json.dumps(snapshot),
            ex=int(_TTL_SEC),
        )
    except Exception:
        logger.warning("Redis quota rule cache write failed", exc_info=True)


async def _get_redis_client():
    try:
        from libs.db.redis import get_redis_client

        return await get_redis_client()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_actor_role_hash(
    *,
    is_team_admin: bool,
    is_platform_admin: bool,
    team_role: str,
) -> str:
    """为不同权限角色生成稳定哈希，确保缓存隔离。"""
    parts = f"ta={is_team_admin}:pa={is_platform_admin}:tr={team_role}"
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


async def get_cached_quota_rules(
    team_id: uuid.UUID,
    *,
    actor_role_hash: str,
    filters: object | None = None,
) -> list[QuotaRuleReadModel] | None:
    """尝试命中配额规则缓存；命中返回反序列化后的规则列表，未命中返回 None。"""
    version = await _get_version(team_id)
    cache_key = _build_cache_key(
        team_id, actor_role_hash=actor_role_hash, filter_hash=_filter_hash(filters)
    )

    local_hit = _get_local(version, cache_key)
    if local_hit is not None:
        return local_hit

    redis_hit = await _get_redis(version, cache_key)
    if redis_hit is not None:
        _put_local(version, cache_key, redis_hit)
        return redis_hit

    return None


async def put_cached_quota_rules(
    team_id: uuid.UUID,
    rules: list[QuotaRuleReadModel],
    *,
    actor_role_hash: str,
    filters: object | None = None,
) -> None:
    """将配额规则列表写入缓存（L1 + Redis）。"""
    version = await _get_version(team_id)
    cache_key = _build_cache_key(
        team_id, actor_role_hash=actor_role_hash, filter_hash=_filter_hash(filters)
    )
    _put_local(version, cache_key, rules)
    await _put_redis(version, cache_key, rules)


async def invalidate_quota_rule_cache_for_team(team_id: uuid.UUID) -> None:
    """失效指定团队的配额规则缓存：同步清 L1 + 异步 bump Redis 版本号。"""
    clear_local_quota_rule_cache_for_team(team_id)
    await _bump_version(team_id)


__all__ = [
    "build_actor_role_hash",
    "clear_all_local_quota_rule_cache_for_tests",
    "clear_local_quota_rule_cache_for_team",
    "get_cached_quota_rules",
    "invalidate_quota_rule_cache_for_team",
    "put_cached_quota_rules",
]
