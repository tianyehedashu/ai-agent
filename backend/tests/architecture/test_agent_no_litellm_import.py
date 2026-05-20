"""架构守门：Agent 域不得直接依赖 LiteLLM 或运行时 provider API Key。"""

from __future__ import annotations

import ast
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[2] / "domains" / "agent"

FORBIDDEN_IMPORT_ROOTS = frozenset({"litellm"})
FORBIDDEN_ATTR_PREFIXES = (
    "openai_api_key",
    "anthropic_api_key",
    "dashscope_api_key",
    "deepseek_api_key",
    "volcengine_api_key",
    "zhipuai_api_key",
    "volcengine_chat_endpoint_id",
    "volcengine_endpoint_id",
)


def _iter_py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in str(p)]


def test_agent_domain_has_no_litellm_import() -> None:
    violations: list[str] = []
    for path in _iter_py_files(AGENT_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                        violations.append(f"{path}: import {alias.name}")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.split(".")[0] in FORBIDDEN_IMPORT_ROOTS
            ):
                violations.append(f"{path}: from {node.module}")
    assert not violations, "\n".join(violations)


def test_agent_domain_has_no_settings_provider_api_key_access() -> None:
    violations: list[str] = []
    for path in _iter_py_files(AGENT_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "settings"
                and node.attr in FORBIDDEN_ATTR_PREFIXES
            ):
                violations.append(f"{path}: settings.{node.attr}")
    assert not violations, "\n".join(violations)
