"""Presentation 层禁止 raise HTTPException（OpenAI/Anthropic 兼容 mapper 白名单除外）。"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]

_HTTP_EXCEPTION_WHITELIST = frozenset(
    {
        _BACKEND_ROOT / "domains/gateway/presentation/openai_compat_error_map.py",
        _BACKEND_ROOT / "domains/gateway/presentation/anthropic_compat_router.py",
    }
)

_SCAN_ROOTS = (
    _BACKEND_ROOT / "domains",
    _BACKEND_ROOT / "libs/api",
)


def _iter_python_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if p.is_file()]


def _raises_http_exception(node: ast.AST) -> bool:
    if not isinstance(node, ast.Raise) or node.exc is None:
        return False
    exc = node.exc
    if isinstance(exc, ast.Call):
        func = exc.func
        if isinstance(func, ast.Name) and func.id == "HTTPException":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "HTTPException":
            return True
    return False


def _find_http_exception_raises(path: Path) -> list[int]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    return [node.lineno for node in ast.walk(tree) if _raises_http_exception(node)]


@pytest.mark.unit
def test_presentation_layers_do_not_raise_http_exception() -> None:
    violations: list[str] = []
    for root in _SCAN_ROOTS:
        if not root.exists():
            continue
        for path in _iter_python_files(root):
            resolved = path.resolve()
            if resolved in _HTTP_EXCEPTION_WHITELIST:
                continue
            lines = _find_http_exception_raises(resolved)
            for line in lines:
                rel = resolved.relative_to(_BACKEND_ROOT)
                violations.append(f"{rel}:{line}")
    assert not violations, "HTTPException raise 仅允许白名单 compat mapper:\n" + "\n".join(
        violations
    )
