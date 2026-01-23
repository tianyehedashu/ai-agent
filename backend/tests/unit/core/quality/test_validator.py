"""
Code Validator 单元测试
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from domains.studio.infrastructure.quality.types import Severity, ValidationIssue
from domains.studio.infrastructure.quality.validator import CodeValidator, ValidationResult


@pytest.mark.unit
class TestCodeValidator:
    """Code Validator 测试"""

    @pytest.fixture
    def validator(self):
        """创建验证器实例"""
        return CodeValidator()

    @pytest.mark.asyncio
    async def test_validate_syntax_valid(self, validator):
        """测试: 验证有效语法"""
        # Arrange
        code = "def hello():\n    return 'world'"

        # Act
        result = await validator.validate(
            code, check_syntax=True, check_types=False, check_lint=False
        )

        # Assert
        assert result.is_valid is True
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_validate_syntax_invalid(self, validator):
        """测试: 验证无效语法"""
        # Arrange
        code = "def hello(\n    return 'world'"  # 语法错误

        # Act
        result = await validator.validate(
            code, check_syntax=True, check_types=False, check_lint=False
        )

        # Assert
        assert result.is_valid is False
        assert result.errors > 0
        assert any(issue.severity == Severity.ERROR for issue in result.issues)

    @pytest.mark.asyncio
    async def test_validate_with_lsp(self, validator):
        """测试: 使用 LSP 进行类型检查"""
        # Arrange
        code = "def add(a: int, b: int) -> int:\n    return a + b"

        # Mock LSP
        mock_lsp = AsyncMock()
        mock_lsp.get_diagnostics = AsyncMock(return_value=[])
        validator.lsp = mock_lsp

        # Act
        await validator.validate(code, check_types=True, check_syntax=False, check_lint=False)

        # Assert
        mock_lsp.get_diagnostics.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_with_architecture(self, validator):
        """测试: 使用架构验证器"""
        # Arrange
        code = "def hello():\n    return 'world'"

        # Mock 架构验证器
        mock_arch = MagicMock()
        mock_arch.validate = MagicMock(return_value=[])
        validator.arch_validator = mock_arch

        # Act
        await validator.validate(code, check_architecture=True, check_syntax=False)

        # Assert
        mock_arch.validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_disabled_checks(self, validator):
        """测试: 禁用某些检查"""
        # Arrange
        code = "def hello():\n    return 'world'"

        # Act
        result = await validator.validate(
            code,
            check_syntax=False,
            check_types=False,
            check_lint=False,
            check_architecture=False,
        )

        # Assert
        # 所有检查都禁用时，应该没有验证
        assert result.is_valid is True

    def test_validation_result_add_issue(self):
        """测试: ValidationResult 添加问题"""
        # Arrange
        result = ValidationResult(is_valid=True)
        issue = ValidationIssue(
            line=1,
            column=1,
            severity=Severity.ERROR,
            message="Test error",
            code="E001",
            source="syntax",
        )

        # Act
        result.add_issue(issue)

        # Assert
        assert len(result.issues) == 1
        assert result.errors == 1
        assert result.is_valid is False

    def test_validation_result_add_warning(self):
        """测试: ValidationResult 添加警告"""
        # Arrange
        result = ValidationResult(is_valid=True)
        issue = ValidationIssue(
            line=1,
            column=1,
            severity=Severity.WARNING,
            message="Test warning",
            code="W001",
            source="lint",
        )

        # Act
        result.add_issue(issue)

        # Assert
        assert len(result.issues) == 1
        assert result.warnings == 1
        assert result.is_valid is True  # 警告不影响有效性

    def test_validation_result_multiple_issues(self):
        """测试: ValidationResult 添加多个问题"""
        # Arrange
        result = ValidationResult(is_valid=True)

        # Act
        result.add_issue(
            ValidationIssue(
                line=1,
                column=1,
                severity=Severity.ERROR,
                message="Error 1",
                code="E001",
                source="syntax",
            )
        )
        result.add_issue(
            ValidationIssue(
                line=2,
                column=1,
                severity=Severity.WARNING,
                message="Warning 1",
                code="W001",
                source="lint",
            )
        )
        result.add_issue(
            ValidationIssue(
                line=3,
                column=1,
                severity=Severity.ERROR,
                message="Error 2",
                code="E002",
                source="type",
            )
        )

        # Assert
        assert len(result.issues) == 3
        assert result.errors == 2
        assert result.warnings == 1
        assert result.is_valid is False
