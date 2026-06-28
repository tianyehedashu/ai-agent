"""成员+凭据预算的 Redis 存在性索引（热路径快路径，避免无规则用户每请求查库）。

索引为每个用户一个 SET：``gw:budget_uc:{user_id}`` → 该用户存在专属预算的 ``credential_id`` 字符串集合。
管理面写入成员+凭据预算时 ``add``；Phase2 pre_call 先 ``has`` 判断，命中才进入配置缓存与预扣。

故障语义：索引仅做「快速排除」。若 Redis 不可用，``has`` 返回 ``None`` 表示未知，
调用方应回退到配置缓存查询（不丢正确性）；写入失败仅记日志。
"""

from __future__ import annotations

import uuid

from utils.logging import get_logger

logger = get_logger(__name__)

_INDEX_PREFIX = "gw:budget_uc:"
_INDEX_TTL_SECONDS = 86400 * 35


def _index_key(user_id: uuid.UUID | str) -> str:
    return f"{_INDEX_PREFIX}{user_id}"


async def _client():
    try:
        from libs.db.redis import get_redis_client

        return await get_redis_client()
    except Exception:
        return None


async def add_user_credential(user_id: uuid.UUID, credential_id: uuid.UUID) -> None:
    """登记某用户在某凭据下存在成员+凭据预算（写路径调用，幂等）。"""
    client = await _client()
    if client is None:
        return
    try:
        key = _index_key(user_id)
        await client.sadd(key, str(credential_id))
        await client.expire(key, _INDEX_TTL_SECONDS)
    except Exception:
        logger.warning("user_credential budget index add failed", exc_info=True)


async def has_user_credential(
    user_id: uuid.UUID, credential_id: uuid.UUID
) -> bool | None:
    """该用户在该凭据下是否可能存在专属预算。

    返回 ``True``/``False`` 为索引判定；``None`` 表示索引不可用（调用方应回退查询）。
    """
    client = await _client()
    if client is None:
        return None
    try:
        return bool(await client.sismember(_index_key(user_id), str(credential_id)))
    except Exception:
        logger.warning("user_credential budget index read failed", exc_info=True)
        return None


__all__ = ["add_user_credential", "has_user_credential"]
