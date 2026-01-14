"""
Code Quality Types - 代码质量共享类型

避免循环导入问题，将共享类型放在独立模块中。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


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
