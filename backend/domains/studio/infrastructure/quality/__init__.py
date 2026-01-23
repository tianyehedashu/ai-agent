"""
Code Quality - 代码质量保证系统

提供:
- 代码验证器
- 架构规范检查
- 自动修复
"""

from domains.studio.infrastructure.quality.architecture import ArchitectureValidator
from domains.studio.infrastructure.quality.fixer import CodeFixer
from domains.studio.infrastructure.quality.types import Severity, ValidationIssue
from domains.studio.infrastructure.quality.validator import CodeValidator

__all__ = [
    "ArchitectureValidator",
    "CodeFixer",
    "CodeValidator",
    "Severity",
    "ValidationIssue",
]
