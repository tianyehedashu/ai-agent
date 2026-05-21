"""FastAPI Users PasswordHelper 适配。"""

from __future__ import annotations

from fastapi_users.password import PasswordHelper

from domains.identity.domain.ports.password_hasher import PasswordHasherPort


class FastAPIUsersPasswordHasher:
    def __init__(self) -> None:
        self._helper = PasswordHelper()

    def hash(self, password: str) -> str:
        return self._helper.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        verified, _ = self._helper.verify_and_update(password, hashed)
        return verified


def default_password_hasher() -> PasswordHasherPort:
    return FastAPIUsersPasswordHasher()


__all__ = ["FastAPIUsersPasswordHasher", "default_password_hasher"]
