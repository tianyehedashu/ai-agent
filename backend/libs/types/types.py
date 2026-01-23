"""
Generic Types - 通用泛型工具类型

与业务无关的通用工具类型：
- Result[T]: 类似 Rust 的 Result 类型
- T: 泛型类型变量
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

# ============================================================================
# 泛型类型
# ============================================================================

T = TypeVar("T")


@dataclass
class Result(Generic[T]):
    """
    结果类型 (类似 Rust Result)

    用法:
        result = Result.ok(value)
        result = Result.err("error message")

        if result.is_ok:
            value = result.unwrap()
        else:
            error = result.error
    """

    _value: T | None = None
    _error: str | None = None

    @property
    def is_ok(self) -> bool:
        return self._error is None

    @property
    def is_err(self) -> bool:
        return self._error is not None

    @property
    def error(self) -> str | None:
        return self._error

    def unwrap(self) -> T:
        if self._error:
            raise ValueError(self._error)
        if self._value is None:
            raise ValueError("Result value is None")
        return self._value

    def unwrap_or(self, default: T) -> T:
        return self._value if self.is_ok and self._value is not None else default

    def map(self, func: Callable[[T], T]) -> Result[T]:
        if self.is_ok and self._value is not None:
            return Result.ok(func(self._value))
        return Result.err(self._error or "Unknown error")

    @classmethod
    def ok(cls, value: T) -> Result[T]:
        return cls(_value=value)

    @classmethod
    def err(cls, error: str) -> Result[T]:
        return cls(_error=error)
