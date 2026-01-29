"""
API Key Domain Service - API Key 领域服务

提供 API Key 生成、验证的业务逻辑。
"""

from __future__ import annotations

from base64 import b64decode, b64encode
from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from typing import Protocol

from cryptography.fernet import Fernet
from fastapi_users.password import PasswordHelper

from domains.identity.domain.api_key_types import (
    API_KEY_SCOPE_GROUPS,
    ApiKeyFormat,
    ApiKeyScope,
)


class ApiKeyGeneratorProtocol(Protocol):
    """API Key 生成器协议"""

    def generate(self) -> tuple[str, str, str]:
        """生成新的 API Key

        Returns:
            (plain_key, key_id, key_hash)
        """
        ...

    def hash_key(self, key: str) -> str:
        """对 Key 进行哈希"""
        ...

    def verify_key(self, key: str, key_hash: str) -> bool:
        """验证 Key 是否匹配哈希"""
        ...

    def encrypt_key(self, plain_key: str, encryption_key: str) -> str:
        """加密 Key

        Args:
            plain_key: 明文 Key
            encryption_key: 加密密钥（base64 编码的 Fernet 密钥）

        Returns:
            加密后的 Key（base64 编码）
        """
        ...

    def decrypt_key(self, encrypted_key: str, encryption_key: str) -> str:
        """解密 Key

        Args:
            encrypted_key: 加密的 Key（base64 编码）
            encryption_key: 加密密钥（base64 编码的 Fernet 密钥）

        Returns:
            明文 Key
        """
        ...

    @staticmethod
    def derive_encryption_key(secret: str) -> str:
        """从应用密钥派生加密密钥

        Args:
            secret: 应用密钥（如 settings.secret_key）

        Returns:
            base64 编码的 Fernet 密钥
        """
        ...


class ApiKeyGenerator:
    """API Key 生成器实现

    使用 secrets 模块生成加密安全的随机值。
    格式: sk_{key_id}_{secret}
    示例: sk_a1b2c3d4e5f6g7h8_x9y0z1a2b3c4d5e6f7g8h9i0j1k2l3m4n5
    """

    # Fernet 密钥长度为 32 字节（base64 编码后 44 字符）
    ENCRYPTION_KEY_LENGTH = 32

    def __init__(self, encryption_key: str | None = None) -> None:
        self._password_helper = PasswordHelper()
        self._encryption_key = encryption_key

    def _get_fernet(self, encryption_key: str | None = None) -> Fernet:
        """获取 Fernet 加密器

        Args:
            encryption_key: 可选的加密密钥，如果为 None 则使用初始化时传入的密钥

        Returns:
            Fernet 加密器实例
        """
        key = encryption_key or self._encryption_key
        if not key:
            raise ValueError("encryption_key is required for encryption/decryption")
        return Fernet(key.encode() if isinstance(key, str) else key)

    @staticmethod
    def generate_key_id() -> str:
        """生成 Key ID（用于日志识别）"""
        # 使用 hex 编码避免与 _ 分隔符冲突
        # hex 编码每个字节产生 2 个字符
        raw = secrets.token_hex(ApiKeyFormat.KEY_ID_LENGTH // 2)
        return raw[: ApiKeyFormat.KEY_ID_LENGTH]

    @staticmethod
    def generate_secret() -> str:
        """生成随机密钥"""
        raw = secrets.token_hex(ApiKeyFormat.SECRET_LENGTH // 2)
        return raw[: ApiKeyFormat.SECRET_LENGTH]

    def generate(self) -> tuple[str, str, str]:
        """生成完整的 API Key

        Returns:
            (plain_key, key_id, key_hash)
            - plain_key: 完整密钥（仅返回一次）
            - key_id: 标识符（用于日志）
            - key_hash: 哈希值（存储）
        """
        key_id = self.generate_key_id()
        secret = self.generate_secret()
        plain_key = (
            f"{ApiKeyFormat.PREFIX}{ApiKeyFormat.SEPARATOR}{key_id}{ApiKeyFormat.SEPARATOR}{secret}"
        )
        key_hash = self.hash_key(plain_key)
        return plain_key, key_id, key_hash

    def hash_key(self, key: str) -> str:
        """对 Key 进行哈希（使用与密码相同的 bcrypt）"""
        return self._password_helper.hash(key)

    def verify_key(self, key: str, key_hash: str) -> bool:
        """验证 Key 是否匹配哈希"""
        verified, _ = self._password_helper.verify_and_update(key, key_hash)
        return verified

    def encrypt_key(self, plain_key: str, encryption_key: str) -> str:
        """加密 Key

        Args:
            plain_key: 明文 Key
            encryption_key: 加密密钥（base64 编码的 Fernet 密钥）

        Returns:
            加密后的 Key（base64 编码）
        """
        fernet = self._get_fernet(encryption_key)
        encrypted_bytes = fernet.encrypt(plain_key.encode())
        return b64encode(encrypted_bytes).decode()

    def decrypt_key(self, encrypted_key: str, encryption_key: str) -> str:
        """解密 Key

        Args:
            encrypted_key: 加密的 Key（base64 编码）
            encryption_key: 加密密钥（base64 编码的 Fernet 密钥）

        Returns:
            明文 Key
        """
        fernet = self._get_fernet(encryption_key)
        encrypted_bytes = b64decode(encrypted_key.encode())
        decrypted_bytes = fernet.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()

    @staticmethod
    def derive_encryption_key(secret: str) -> str:
        """从应用密钥派生加密密钥

        使用 SHA-256 哈希将任意长度的密钥派生为 32 字节的 Fernet 密钥。

        Args:
            secret: 应用密钥（如 settings.secret_key）

        Returns:
            base64 编码的 Fernet 密钥
        """
        # 使用 SHA-256 生成 32 字节密钥
        key_bytes = hashlib.sha256(secret.encode()).digest()
        return b64encode(key_bytes).decode()


class ApiKeyDomainService:
    """API Key 领域服务

    封装 API Key 相关的业务规则。
    """

    def __init__(self, generator: ApiKeyGeneratorProtocol | None = None) -> None:
        self.generator = generator or ApiKeyGenerator()

    def validate_creation_request(
        self,
        name: str,
        description: str | None,
        scopes: set[ApiKeyScope] | None,
        expires_in_days: int,
    ) -> tuple[datetime, set[ApiKeyScope]]:
        """验证创建请求

        Args:
            name: Key 名称
            description: 描述
            scopes: 作用域集合
            expires_in_days: 有效期（天）

        Returns:
            (expires_at, validated_scopes)
        """
        # 计算过期时间
        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

        # 验证作用域
        validated_scopes = scopes if scopes else API_KEY_SCOPE_GROUPS["read_only"]

        # 业务规则：过期时间不能超过 1 年
        max_expiry = datetime.now(UTC) + timedelta(days=365)
        if expires_at > max_expiry:
            raise ValueError("expires_at cannot exceed 1 year")

        return expires_at, validated_scopes

    def validate_expiry_update(
        self,
        current_expires_at: datetime,
        additional_days: int,
    ) -> datetime:
        """验证过期时间更新

        Args:
            current_expires_at: 当前过期时间
            additional_days: 延长的天数

        Returns:
            新的过期时间
        """
        new_expiry = current_expires_at + timedelta(days=additional_days)

        # 业务规则：总有效期不能超过 1 年
        max_expiry = datetime.now(UTC) + timedelta(days=365)
        if new_expiry > max_expiry:
            raise ValueError("Total expiry cannot exceed 1 year from now")

        return new_expiry

    def is_valid_key_format(self, key: str) -> bool:
        """验证 Key 格式是否有效"""
        try:
            parts = key.split(ApiKeyFormat.SEPARATOR)
            return (
                len(parts) == 3
                and parts[0] == ApiKeyFormat.PREFIX
                and len(parts[1]) == ApiKeyFormat.KEY_ID_LENGTH
            )
        except Exception:
            return False
