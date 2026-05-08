"""
Crypto Utilities - 加密工具

提供对称加密/解密功能，用于安全存储用户 API Key 等敏感信息。
复用 identity 域的 Fernet 加密方案。
"""

from __future__ import annotations

from base64 import b64decode, b64encode
import hashlib

from cryptography.fernet import Fernet


def derive_encryption_key(secret: str) -> str:
    """从应用密钥派生 Fernet 加密密钥

    Args:
        secret: 应用密钥（如 settings.secret_key）

    Returns:
        base64 编码的 32 字节 Fernet 密钥
    """
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return b64encode(key_bytes).decode()


def encrypt_value(plain: str, encryption_key: str) -> str:
    """加密字符串

    Args:
        plain: 明文
        encryption_key: base64 编码的 Fernet 密钥

    Returns:
        加密后的 base64 字符串
    """
    fernet = Fernet(encryption_key.encode())
    encrypted_bytes = fernet.encrypt(plain.encode())
    return b64encode(encrypted_bytes).decode()


def decrypt_value(encrypted: str, encryption_key: str) -> str:
    """解密字符串

    Args:
        encrypted: 加密的 base64 字符串
        encryption_key: base64 编码的 Fernet 密钥

    Returns:
        明文

    Raises:
        InvalidToken: 密钥不匹配或数据损坏
    """
    fernet = Fernet(encryption_key.encode())
    encrypted_bytes = b64decode(encrypted.encode())
    return fernet.decrypt(encrypted_bytes).decode()


def mask_api_key(key: str, visible_prefix: int = 3, visible_suffix: int = 4) -> str:
    """脱敏 API Key 用于展示

    例: sk-abc...xyzw

    Args:
        key: 明文 API Key
        visible_prefix: 前缀可见字符数
        visible_suffix: 后缀可见字符数

    Returns:
        脱敏后的字符串
    """
    if len(key) <= visible_prefix + visible_suffix:
        return "****"
    return f"{key[:visible_prefix]}****{key[-visible_suffix:]}"


__all__ = [
    "decrypt_value",
    "derive_encryption_key",
    "encrypt_value",
    "mask_api_key",
]
