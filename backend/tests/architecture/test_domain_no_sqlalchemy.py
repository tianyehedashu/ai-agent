"""domain 层不得依赖 SQLAlchemy / infrastructure ORM。"""

from __future__ import annotations

import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).resolve().parents[2] / "domains"


def _iter_domain_py_files() -> list[Path]:
    files: list[Path] = []
    for bc in DOMAIN_ROOT.iterdir():
        domain_dir = bc / "domain"
        if domain_dir.is_dir():
            files.extend(p for p in domain_dir.rglob("*.py") if "__pycache__" not in str(p))
    return files


def _is_forbidden_import(module: str | None) -> bool:
    if not module:
        return False
    if module.startswith("sqlalchemy"):
        return True
    if module.startswith("domains.") and ".infrastructure" in module:
        return True
    return False


def _relative_domain_path(path: Path) -> str:
    return path.relative_to(DOMAIN_ROOT.parent).as_posix()


def test_domain_modules_have_no_sqlalchemy_or_infrastructure_imports() -> None:
    """仅检查模块顶层 import（函数内懒加载不计入，后续迁 application）。"""
    violations: list[str] = []
    for path in _iter_domain_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden_import(alias.name):
                        violations.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and _is_forbidden_import(node.module):
                violations.append(f"{path}: from {node.module}")
    assert not violations, "\n".join(violations)
