"""Identity Domain - Application Layer（延迟导出，避免与 infrastructure 循环导入）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.identity.application.ports import IdentityApplicationPort

if TYPE_CHECKING:
    from domains.identity.application.user_use_case import UserUseCase

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "ANONYMOUS_COOKIE_MAX_AGE": (
        "domains.identity.application.principal_service",
        "ANONYMOUS_COOKIE_MAX_AGE",
    ),
    "ANONYMOUS_USER_COOKIE": (
        "domains.identity.application.principal_service",
        "ANONYMOUS_USER_COOKIE",
    ),
    "UserUseCase": ("domains.identity.application.user_use_case", "UserUseCase"),
    "get_principal": ("domains.identity.application.principal_service", "get_principal"),
    "get_principal_optional": (
        "domains.identity.application.principal_service",
        "get_principal_optional",
    ),
}

__all__ = [
    "ANONYMOUS_COOKIE_MAX_AGE",
    "ANONYMOUS_USER_COOKIE",
    "IdentityApplicationPort",
    "UserUseCase",
    "get_principal",
    "get_principal_optional",
]


def __getattr__(name: str) -> object:
    if name not in _LAZY_EXPORTS:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    module_path, attr = _LAZY_EXPORTS[name]
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, attr)
