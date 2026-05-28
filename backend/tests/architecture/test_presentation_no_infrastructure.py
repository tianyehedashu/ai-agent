"""presentation 层不得新增对 infrastructure 的顶层 import（存量 allowlist）。"""

from __future__ import annotations

import ast
from pathlib import Path

PRESENTATION_ROOT = Path(__file__).resolve().parents[2] / "domains"

_PRESENTATION_IMPORT_ALLOWLIST = frozenset(
    {
        "domains/agent/presentation/chat_router.py",
        "domains/agent/presentation/execution_router.py",
        "domains/agent/presentation/system_router.py",
        "domains/agent/presentation/tools_router.py",
        "domains/gateway/presentation/routers/pricing.py",
        "domains/identity/presentation/middleware.py",
        "domains/identity/presentation/router.py",
        "domains/session/presentation/session_router.py",
    }
)


def _iter_presentation_py_files() -> list[Path]:
    files: list[Path] = []
    for bc in PRESENTATION_ROOT.iterdir():
        presentation_dir = bc / "presentation"
        if presentation_dir.is_dir():
            files.extend(
                p for p in presentation_dir.rglob("*.py") if "__pycache__" not in str(p)
            )
    return files


def _relative_path(path: Path) -> str:
    return path.relative_to(PRESENTATION_ROOT.parent).as_posix()


def _is_forbidden_import(module: str | None) -> bool:
    if not module:
        return False
    return module.startswith("domains.") and ".infrastructure" in module


def test_presentation_has_no_new_infrastructure_imports() -> None:
    violations: list[str] = []
    for path in _iter_presentation_py_files():
        rel = _relative_path(path)
        if rel in _PRESENTATION_IMPORT_ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden_import(alias.name):
                        violations.append(f"{rel}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and _is_forbidden_import(node.module):
                violations.append(f"{rel}: from {node.module}")
    assert not violations, "\n".join(violations)
