"""架构守门：Agent 对话路径不得直接依赖 Gateway 思考/出站策略 domain 模块。"""

from __future__ import annotations

import ast
from pathlib import Path

# 已有文件可能依赖 gateway.domain.types / scenario_defaults_policy；本测试仅约束新策略模块。
CHECK_PATHS = [
    Path(__file__).resolve().parents[2] / "domains" / "agent" / "application" / "chat_agent_run.py",
    Path(__file__).resolve().parents[2] / "domains" / "agent" / "application" / "chat_use_case.py",
    Path(__file__).resolve().parents[2]
    / "domains"
    / "agent"
    / "infrastructure"
    / "llm"
    / "agent_llm_facade.py",
]
FORBIDDEN_MODULES = frozenset(
    {
        "domains.gateway.domain.thinking_param",
        "domains.gateway.domain.temperature_policy",
        "domains.gateway.domain.policies.invocation_policy",
    }
)


def test_agent_chat_path_has_no_invocation_policy_domain_import() -> None:
    violations: list[str] = []
    for path in CHECK_PATHS:
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_MODULES:
                        violations.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module in FORBIDDEN_MODULES:
                violations.append(f"{path}: from {node.module}")
    assert not violations, "\n".join(violations)
