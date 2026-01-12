"""
Crypto Utilities - 加密工具
"""

import hashlib
import secrets
import uuid
from base64 import b64decode, b64encode
from typing import Any


def generate_id() -> str:
    """生成唯一 ID"""
    return str(uuid.uuid4())


def generate_short_id(length: int = 8) -> str:
    """生成短 ID"""
    return secrets.token_urlsafe(length)[:length]


def generate_secret(length: int = 32) -> str:
    """生成密钥"""
    return secrets.token_hex(length)


def hash_string(s: str, algorithm: str = "sha256") -> str:
    """哈希字符串"""
    h = hashlib.new(algorithm)
    h.update(s.encode())
    return h.hexdigest()


def encode_base64(data: bytes) -> str:
    """Base64 编码"""
    return b64encode(data).decode()


def decode_base64(data: str) -> bytes:
    """Base64 解码"""
    return b64decode(data)
