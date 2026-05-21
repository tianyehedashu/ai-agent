"""
Password Domain Service - 密码领域服务

包含密码哈希和验证的业务逻辑"""

from __future__ import annotations

from domains.identity.domain.ports.password_hasher import PasswordHasherPort


def _default_password_hasher() -> PasswordHasherPort:
    from domains.identity.infrastructure.password_hasher_fastapi_users import (
        default_password_hasher,
    )

    return default_password_hasher()


class PasswordService:
    """密码领域服务

    处理密码的哈希和验证"""

    def __init__(self, hasher: PasswordHasherPort | None = None) -> None:
        self._hasher = hasher or _default_password_hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        return self._hasher.verify(password, hashed)
