"""
Architecture Validator - 架构规范检查器

检查代码是否符合项目架构规范:
- ARCH001: Agent 类必须继承 BaseAgent
- ARCH002: Tool 类必须实现 ToolProtocol
- ARCH003: Service 类必须使用依赖注入
- SEC001: 禁止使用 eval/exec
- SEC002: 禁止硬编码敏感信息
"""

import ast
from dataclasses import dataclass

from domains.studio.infrastructure.quality.types import Severity, ValidationIssue
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ArchitectureRule:
    """架构规则"""

    code: str
    name: str
    description: str
    severity: Severity = Severity.ERROR


# 预定义规则
RULES = {
    "ARCH001": ArchitectureRule(
        code="ARCH001",
        name="agent-inheritance",
        description="Agent 类必须继承 BaseAgent",
    ),
    "ARCH002": ArchitectureRule(
        code="ARCH002",
        name="tool-protocol",
        description="Tool 类必须实现 BaseTool",
    ),
    "ARCH003": ArchitectureRule(
        code="ARCH003",
        name="service-injection",
        description="Service 类应使用依赖注入",
        severity=Severity.WARNING,
    ),
    "SEC001": ArchitectureRule(
        code="SEC001",
        name="no-eval",
        description="禁止使用 eval/exec",
    ),
    "SEC002": ArchitectureRule(
        code="SEC002",
        name="no-hardcoded-secrets",
        description="禁止硬编码敏感信息",
        severity=Severity.WARNING,
    ),
}


class ArchitectureValidator:
    """
    架构规范检查器

    基于 AST 分析代码结构
    """

    def __init__(
        self,
        enabled_rules: list[str] | None = None,
        disabled_rules: list[str] | None = None,
    ) -> None:
        self.enabled_rules = enabled_rules
        self.disabled_rules = disabled_rules or []

    def validate(self, code: str) -> list[ValidationIssue]:
        """
        验证代码架构规范

        Args:
            code: Python 代码

        Returns:
            问题列表
        """
        issues = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues  # 语法错误由其他检查器处理

        # 运行各项检查
        issues.extend(self._check_agent_inheritance(tree))
        issues.extend(self._check_tool_implementation(tree))
        issues.extend(self._check_eval_usage(tree))
        issues.extend(self._check_hardcoded_secrets(tree))

        # 过滤禁用的规则
        issues = [i for i in issues if i.code not in self.disabled_rules]

        # 如果指定了启用规则，只保留这些规则
        if self.enabled_rules:
            issues = [i for i in issues if i.code in self.enabled_rules]

        return issues

    def _check_agent_inheritance(self, tree: ast.AST) -> list[ValidationIssue]:
        """检查 Agent 类继承"""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "Agent" in node.name and node.name != "BaseAgent":
                # 检查是否继承 BaseAgent
                base_names = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_names.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        base_names.append(base.attr)

                if "BaseAgent" not in base_names and "AgentEngine" not in base_names:
                    issues.append(
                        ValidationIssue(
                            line=node.lineno,
                            column=node.col_offset,
                            severity=RULES["ARCH001"].severity,
                            message=f"类 '{node.name}' 应该继承 BaseAgent",
                            code="ARCH001",
                            source="architecture",
                        )
                    )

        return issues

    def _check_tool_implementation(self, tree: ast.AST) -> list[ValidationIssue]:
        """检查 Tool 类实现"""
        issues = []

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ClassDef)
                and "Tool" in node.name
                and node.name not in ("BaseTool", "ToolProtocol")
            ):
                # 检查是否继承 BaseTool
                base_names = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_names.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        base_names.append(base.attr)

                if "BaseTool" not in base_names:
                    issues.append(
                        ValidationIssue(
                            line=node.lineno,
                            column=node.col_offset,
                            severity=RULES["ARCH002"].severity,
                            message=f"类 '{node.name}' 应该继承 BaseTool",
                            code="ARCH002",
                            source="architecture",
                        )
                    )

        return issues

    def _check_eval_usage(self, tree: ast.AST) -> list[ValidationIssue]:
        """检查 eval/exec 使用"""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in ("eval", "exec"):
                    issues.append(
                        ValidationIssue(
                            line=node.lineno,
                            column=node.col_offset,
                            severity=RULES["SEC001"].severity,
                            message=f"禁止使用 {func_name}()，存在安全风险",
                            code="SEC001",
                            source="architecture",
                        )
                    )

        return issues

    def _check_hardcoded_secrets(self, tree: ast.AST) -> list[ValidationIssue]:
        """检查硬编码敏感信息"""
        issues = []

        # 敏感关键词
        sensitive_keywords = [
            "password",
            "secret",
            "api_key",
            "apikey",
            "token",
            "private_key",
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id.lower()

                        # 检查变量名是否包含敏感关键词
                        for keyword in sensitive_keywords:
                            if keyword in var_name:
                                # 检查是否直接赋值字符串 (排除空字符串)
                                if (
                                    isinstance(node.value, ast.Constant)
                                    and isinstance(node.value.value, str)
                                    and len(node.value.value) > 5
                                ):
                                    issues.append(
                                        ValidationIssue(
                                            line=node.lineno,
                                            column=node.col_offset,
                                            severity=RULES["SEC002"].severity,
                                            message=(
                                                f"变量 '{target.id}' 可能包含硬编码的敏感信息，"
                                                "请使用环境变量"
                                            ),
                                            code="SEC002",
                                            source="architecture",
                                        )
                                    )
                                break

        return issues
