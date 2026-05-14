"""
VirtualKeyGenerator - 虚拟 Key 生成与验证

格式：sk-gw-{key_id:16}-{secret:32}
- 前缀 `sk-gw-` 区分于业务管理 API 的 `sk-`
- key_id：用于日志展示与快速查找
- secret：随机部分，bcrypt hash 后存储；明文加密一份用于"显示完整 Key"
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

VKEY_PREFIX = "sk-gw-"
VKEY_KEY_ID_LENGTH = 16
VKEY_SECRET_LENGTH = 32
VKEY_FULL_LENGTH = len(VKEY_PREFIX) + VKEY_KEY_ID_LENGTH + 1 + VKEY_SECRET_LENGTH


def generate_vkey() -> tuple[str, str, str]:
    """生成新的虚拟 Key

    Returns:
        (plain_key, key_id, key_hash)
        - plain_key: 完整明文（仅返回一次）
        - key_id: 16 字符随机标识，用于日志与查找
        - key_hash: HMAC-SHA256 哈希，存库
    """
    key_id = secrets.token_hex(VKEY_KEY_ID_LENGTH // 2)[:VKEY_KEY_ID_LENGTH]
    secret_part = secrets.token_hex(VKEY_SECRET_LENGTH // 2)[:VKEY_SECRET_LENGTH]
    plain_key = f"{VKEY_PREFIX}{key_id}-{secret_part}"
    key_hash = hash_vkey(plain_key)
    return plain_key, key_id, key_hash


def hash_vkey(key: str) -> str:
    """对 Key 进行哈希（HMAC-SHA256，确定性，便于按 hash 查找）

    使用确定性哈希而非 bcrypt，因为：
    - vkey 验证频次极高（每次 /v1/* 调用），bcrypt 性能不够
    - 长度 32+ 的随机 secret 已经足够安全
    - 通过 PEPPER（应用 secret_key）防止彩虹表攻击
    """
    pepper = _get_pepper()
    return hmac.new(pepper.encode(), key.encode(), hashlib.sha256).hexdigest()


def verify_vkey(key: str, key_hash: str) -> bool:
    """验证 Key 与 hash 是否匹配（恒定时间比较）"""
    expected = hash_vkey(key)
    return hmac.compare_digest(expected, key_hash)


def is_vkey_format(key: str) -> bool:
    """判断字符串是否符合 vkey 格式"""
    if not key.startswith(VKEY_PREFIX):
        return False
    body = key[len(VKEY_PREFIX) :]
    if "-" not in body:
        return False
    parts = body.split("-", 1)
    if len(parts) != 2:
        return False
    key_id, secret_part = parts
    if len(key_id) != VKEY_KEY_ID_LENGTH or len(secret_part) != VKEY_SECRET_LENGTH:
        return False
    return all(c in "0123456789abcdef" for c in key_id + secret_part)


def extract_key_id(key: str) -> str | None:
    """从完整 vkey 中提取 key_id（用于按 key_id 索引快速预筛）"""
    if not is_vkey_format(key):
        return None
    body = key[len(VKEY_PREFIX) :]
    return body.split("-", 1)[0]


def mask_vkey(key: str) -> str:
    """掩码显示"""
    if not key.startswith(VKEY_PREFIX) or len(key) < len(VKEY_PREFIX) + 8:
        return "****"
    return f"{key[: len(VKEY_PREFIX) + 4]}...{key[-4:]}"


_pepper_cache: str | None = None


def _get_pepper() -> str:
    """获取 hash pepper（来自应用 secret_key）

    缓存避免每次都读 settings；测试环境会自动重新加载。
    """
    global _pepper_cache  # pylint: disable=global-statement
    if _pepper_cache is None:
        from bootstrap.config import settings  # pylint: disable=import-outside-toplevel

        _pepper_cache = "vkey:" + settings.secret_key.get_secret_value()
    return _pepper_cache


def reset_pepper_cache() -> None:
    """测试用：重置 pepper 缓存"""
    global _pepper_cache  # pylint: disable=global-statement
    _pepper_cache = None


__all__ = [
    "VKEY_FULL_LENGTH",
    "VKEY_KEY_ID_LENGTH",
    "VKEY_PREFIX",
    "VKEY_SECRET_LENGTH",
    "extract_key_id",
    "generate_vkey",
    "hash_vkey",
    "is_vkey_format",
    "mask_vkey",
    "reset_pepper_cache",
    "verify_vkey",
]
