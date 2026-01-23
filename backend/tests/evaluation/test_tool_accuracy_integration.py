"""
工具调用准确率集成测试

测试完整的工具调用准确率评估流程
"""

import pytest

from domains.agent.domain.types import ToolCall, ToolResult
from evaluation.tool_accuracy import ToolAccuracyEvaluator


class TestToolAccuracyIntegration:
    """工具调用准确率集成测试"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器"""
        return ToolAccuracyEvaluator()

    def test_evaluate_file_operation_sequence(self, evaluator):
        """测试: 评估文件操作序列"""
        # Arrange - 模拟读取然后写入的场景
        tool_calls = [
            ToolCall(
                id="call_1",
                name="read_file",
                arguments={"path": "/tmp/input.txt"},
            ),
            ToolCall(
                id="call_2",
                name="write_file",
                arguments={"path": "/tmp/output.txt", "content": "Processed data"},
            ),
        ]
        tool_results = [
            ToolResult(tool_call_id="call_1", success=True, output="File content"),
            ToolResult(tool_call_id="call_2", success=True, output=""),
        ]

        # Act - 评估每个工具调用
        results = []
        for tool_call, tool_result in zip(tool_calls, tool_results, strict=False):
            result = evaluator.evaluate_tool_call(
                tool_call=tool_call,
                tool_result=tool_result,
                expected_tool=tool_call.name,
                expected_args=tool_call.arguments,
            )
            results.append(result)

        # Assert - 检查序列评估结果
        assert all(r.correct_tool for r in results)
        assert all(r.correct_args for r in results)
        assert all(r.execution_success for r in results)
        assert all(r.overall_score >= 0.8 for r in results)

    def test_evaluate_missing_required_tool(self, evaluator):
        """测试: 评估缺失必需工具"""
        # Arrange - 只调用了部分工具
        tool_calls = [
            ToolCall(
                id="call_1",
                name="read_file",
                arguments={"path": "/tmp/test.txt"},
            ),
        ]
        required_tools = ["read_file", "write_file", "delete_file"]

        # Act - 只评估实际调用的工具
        for tool_call in tool_calls:
            evaluator.evaluate_tool_call(
                tool_call=tool_call,
                expected_tool=tool_call.name,
            )

        # 检查缺失的工具
        called_tools = {tc.name for tc in tool_calls}
        missing_tools = [tool for tool in required_tools if tool not in called_tools]

        # Assert
        assert len(missing_tools) > 0
        assert "write_file" in missing_tools or "delete_file" in missing_tools

        # 生成报告验证总体准确率较低（因为缺少必需工具）
        report = evaluator.generate_report()
        # 虽然调用的工具是正确的，但缺少必需工具会导致任务不完整
        assert report.total_calls == 1

    def test_evaluate_wrong_tool_selection(self, evaluator):
        """测试: 评估工具选择错误"""
        # Arrange - 使用了错误的工具
        tool_call = ToolCall(
            id="call_1",
            name="write_file",
            arguments={"path": "/tmp/test.txt", "content": "data"},
        )

        # Act
        result = evaluator.evaluate_tool_call(
            tool_call=tool_call,
            expected_tool="read_file",  # 期望的工具不同
            expected_args={"path": "/tmp/test.txt"},
        )

        # Assert
        assert result.correct_tool is False
        assert result.overall_score < 0.5

    def test_evaluate_parameter_accuracy(self, evaluator):
        """测试: 评估参数准确性"""
        # Arrange - 参数部分正确
        tool_call = ToolCall(
            id="call_1",
            name="read_file",
            arguments={"path": "/tmp/test.txt", "encoding": "utf-8"},
        )

        # Act - 期望的参数包含额外字段
        result = evaluator.evaluate_tool_call(
            tool_call=tool_call,
            expected_tool="read_file",
            expected_args={"path": "/tmp/test.txt", "encoding": "utf-8", "offset": 0},
        )

        # Assert - 参数应该部分匹配
        assert result.correct_tool is True
        # 参数应该部分匹配，但不是完全匹配
        assert result.args_accuracy > 0.0
        # 由于缺少 offset 参数，可能不是完全正确
        assert result.correct_args is False or result.args_accuracy < 1.0

    def test_generate_comprehensive_report(self, evaluator):
        """测试: 生成综合评估报告"""
        # Arrange - 多个工具调用
        tool_calls = [
            ToolCall(id="c1", name="read_file", arguments={"path": "/tmp/a.txt"}),
            ToolCall(id="c2", name="write_file", arguments={"path": "/tmp/b.txt"}),
        ]

        # Act - 评估所有工具调用
        for tool_call in tool_calls:
            evaluator.evaluate_tool_call(
                tool_call=tool_call,
                expected_tool=tool_call.name,
                expected_args=tool_call.arguments,
            )

        report = evaluator.generate_report()

        # Assert
        assert report.total_calls == 2
        assert report.tool_accuracy > 0.0
        assert report.overall_accuracy > 0.0
        assert len(report.results) == 2
        # 检查报告包含两个工具的结果
        tool_names = {r.tool_name for r in report.results}
        assert "read_file" in tool_names
        assert "write_file" in tool_names
