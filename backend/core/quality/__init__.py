"""
Code Quality - 代码质量保证系统

提供:
- 代码验证器
- 架构规范检查
- 自动修复
"""

from core.quality.architecture import ArchitectureValidator
from core.quality.fixer import CodeFixer
from core.quality.types import Severity, ValidationIssue
from core.quality.validator import CodeValidator

__all__ = [
    "ArchitectureValidator",
    "CodeFixer",
    "CodeValidator",
    "Severity",
    "ValidationIssue",
]
