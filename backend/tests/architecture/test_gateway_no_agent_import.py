"""架构守门：Gateway 域不得反向依赖 Agent 域。"""

from __future__ import annotations

import ast
from pathlib import Path

GATEWAY_ROOT = Path(__file__).resolve().parents[2] / "domains" / "gateway"
FORBIDDEN_PREFIX = "domains.agent"


def _iter_py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in str(p)]


def test_gateway_domain_has_no_agent_import() -> None:
    violations: list[str] = []
    for path in _iter_py_files(GATEWAY_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(FORBIDDEN_PREFIX):
                        violations.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
                FORBIDDEN_PREFIX
            ):
                violations.append(f"{path}: from {node.module}")
    assert not violations, "\n".join(violations)
