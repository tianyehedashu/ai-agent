"""
工具调用准确率评估测试
"""
# pylint: disable=protected-access  # 测试代码需要访问私有方法

import pytest

from core.types import ToolCall, ToolResult
from evaluation.tool_accuracy import ToolAccuracyEvaluator


class TestToolAccuracyEvaluator:
    """工具调用准确率评估器测试"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器"""
        return ToolAccuracyEvaluator()

    def test_evaluate_correct_tool_and_args(self, evaluator):
        """测试: 正确的工具和参数"""
        # Arrange
        tool_call = ToolCall(
            id="call_1",
            name="read_file",
            arguments={"path": "/tmp/test.txt"},
        )
        tool_result = ToolResult(
            tool_call_id="call_1",
            success=True,
            output="File content",
        )

        # Act
        result = evaluator.evaluate_tool_call(
            tool_call=tool_call,
            tool_result=tool_result,
            expected_tool="read_file",
            expected_args={"path": "/tmp/test.txt"},
        )

        # Assert
        assert result.correct_tool is True
        assert result.correct_args is True
        assert result.args_accuracy == 1.0
        assert result.execution_success is True
        assert result.overall_score >= 0.9

    def test_evaluate_wrong_tool(self, evaluator):
        """测试: 错误的工具选择"""
        # Arrange
        tool_call = ToolCall(
            id="call_1",
            name="write_file",  # 错误工具
            arguments={"path": "/tmp/test.txt"},
        )

        # Act
        result = evaluator.evaluate_tool_call(
            tool_call=tool_call,
            expected_tool="read_file",
        )

        # Assert
        assert result.correct_tool is False
        assert result.overall_score < 0.5

    def test_evaluate_wrong_args(self, evaluator):
        """测试: 错误的参数"""
        # Arrange
        tool_call = ToolCall(
            id="call_1",
            name="read_file",
            arguments={"path": "/tmp/wrong.txt"},  # 错误路径
        )

        # Act
        result = evaluator.evaluate_tool_call(
            tool_call=tool_call,
            expected_tool="read_file",
            expected_args={"path": "/tmp/test.txt"},
        )

        # Assert
        assert result.correct_tool is True
        assert result.correct_args is False
        assert result.args_accuracy < 1.0

    def test_evaluate_partial_args_match(self, evaluator):
        """测试: 部分参数匹配"""
        # Arrange
        tool_call = ToolCall(
            id="call_1",
            name="read_file",
            arguments={"path": "/tmp/test.txt", "encoding": "utf-8"},
        )

        # Act
        result = evaluator.evaluate_tool_call(
            tool_call=tool_call,
            expected_tool="read_file",
            expected_args={"path": "/tmp/test.txt"},  # 只期望 path
        )

        # Assert
        assert result.correct_tool is True
        # 应该匹配，因为包含期望的参数
        assert result.args_accuracy > 0.5

    def test_evaluate_execution_failure(self, evaluator):
        """测试: 执行失败"""
        # Arrange
        tool_call = ToolCall(
            id="call_1",
            name="read_file",
            arguments={"path": "/tmp/test.txt"},
        )
        tool_result = ToolResult(
            tool_call_id="call_1",
            success=False,
            output="",
            error="File not found",
        )

        # Act
        result = evaluator.evaluate_tool_call(
            tool_call=tool_call,
            tool_result=tool_result,
            expected_tool="read_file",
        )

        # Assert
        assert result.correct_tool is True
        assert result.execution_success is False
        assert result.overall_score < 0.7

    def test_generate_report(self, evaluator):
        """测试: 生成评估报告"""
        # Arrange
        tool_calls = [
            ToolCall(id="call_1", name="read_file", arguments={"path": "/tmp/test.txt"}),
            ToolCall(id="call_2", name="write_file", arguments={"path": "/tmp/output.txt"}),
        ]

        for tool_call in tool_calls:
            evaluator.evaluate_tool_call(tool_call, expected_tool=tool_call.name)

        # Act
        report = evaluator.generate_report()

        # Assert
        assert report.total_calls == 2
        assert report.tool_accuracy == 1.0
        assert report.overall_accuracy > 0.0

    def test_string_similarity(self, evaluator):
        """测试: 字符串相似度计算"""
        # 完全匹配
        assert evaluator._string_similarity("hello", "hello") == 1.0

        # 包含关系
        assert evaluator._string_similarity("hello", "hello world") > 0.5

        # 不同字符串
        assert evaluator._string_similarity("hello", "world") < 0.5

    def test_numeric_similarity(self, evaluator):
        """测试: 数值相似度计算"""
        # 完全匹配
        assert evaluator._numeric_similarity(100, 100) == 1.0

        # 接近值
        assert evaluator._numeric_similarity(100, 101) > 0.9

        # 差异较大
        assert evaluator._numeric_similarity(100, 200) < 0.6
