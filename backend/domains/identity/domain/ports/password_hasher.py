"""密码哈希端口（domain 层，无 FastAPI Users 依赖）。"""

from __future__ import annotations

from typing import Protocol


class PasswordHasherPort(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, hashed: str) -> bool: ...


__all__ = ["PasswordHasherPort"]
