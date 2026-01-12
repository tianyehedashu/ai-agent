"""
Code Validator - 代码验证器

综合验证:
- 语法检查 (ast.parse)
- 类型检查 (Pyright)
- Lint 检查 (Ruff)
- 架构规范检查
"""

import ast
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.lsp.proxy import LSPProxy
from core.quality.architecture import ArchitectureValidator
from utils.logging import get_logger

logger = get_logger(__name__)


class Severity(str, Enum):
    """严重性级别"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


@dataclass
class ValidationIssue:
    """验证问题"""

    line: int
    column: int
    severity: Severity
    message: str
    code: str
    source: str  # syntax, type, lint, architecture
    fix: dict[str, Any] | None = None


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    errors: int = 0
    warnings: int = 0

    def add_issue(self, issue: ValidationIssue) -> None:
        """添加问题"""
        self.issues.append(issue)
        if issue.severity == Severity.ERROR:
            self.errors += 1
            self.is_valid = False
        elif issue.severity == Severity.WARNING:
            self.warnings += 1


class CodeValidator:
    """
    代码验证器

    提供多层次的代码质量检查
    """

    def __init__(
        self,
        lsp_proxy: LSPProxy | None = None,
        arch_validator: ArchitectureValidator | None = None,
    ) -> None:
        self.lsp = lsp_proxy or LSPProxy()
        self.arch_validator = arch_validator or ArchitectureValidator()

    async def validate(
        self,
        code: str,
        file_path: str = "code.py",
        check_syntax: bool = True,
        check_types: bool = True,
        check_lint: bool = True,
        check_architecture: bool = True,
    ) -> ValidationResult:
        """
        验证代码

        Args:
            code: Python 代码
            file_path: 文件路径
            check_syntax: 是否检查语法
            check_types: 是否检查类型
            check_lint: 是否检查 Lint
            check_architecture: 是否检查架构规范

        Returns:
            验证结果
        """
        result = ValidationResult(is_valid=True)

        # 1. 语法检查
        if check_syntax:
            syntax_issues = self._check_syntax(code)
            for issue in syntax_issues:
                result.add_issue(issue)

            # 如果有语法错误，后续检查可能无法进行
            if result.errors > 0:
                return result

        # 2. 类型检查 + Lint 检查
        if check_types or check_lint:
            try:
                diagnostics = await self.lsp.get_diagnostics(file_path, code)
                for diag in diagnostics:
                    source = diag.get("source", "unknown")

                    # 根据配置过滤
                    if source == "pyright" and not check_types:
                        continue
                    if source == "ruff" and not check_lint:
                        continue

                    result.add_issue(
                        ValidationIssue(
                            line=diag.get("line", 0),
                            column=diag.get("column", 0),
                            severity=self._convert_severity(diag.get("severity", "error")),
                            message=diag.get("message", ""),
                            code=diag.get("code", ""),
                            source=source,
                            fix=diag.get("fix"),
                        )
                    )
            except Exception as e:
                logger.warning(f"LSP diagnostics failed: {e}")

        # 3. 架构规范检查
        if check_architecture:
            arch_issues = self.arch_validator.validate(code)
            for issue in arch_issues:
                result.add_issue(issue)

        return result

    def _check_syntax(self, code: str) -> list[ValidationIssue]:
        """检查语法"""
        issues = []

        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(
                ValidationIssue(
                    line=e.lineno or 1,
                    column=e.offset or 0,
                    severity=Severity.ERROR,
                    message=str(e.msg),
                    code="E999",
                    source="syntax",
                )
            )

        return issues

    def _convert_severity(self, severity: str) -> Severity:
        """转换严重性级别"""
        mapping = {
            "error": Severity.ERROR,
            "warning": Severity.WARNING,
            "info": Severity.INFO,
            "hint": Severity.HINT,
        }
        return mapping.get(severity.lower(), Severity.ERROR)

    async def validate_quick(self, code: str) -> bool:
        """
        快速验证 (仅语法检查)

        Args:
            code: Python 代码

        Returns:
            是否有效
        """
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False
