"""
工具调用准确率集成测试

测试完整的工具调用准确率评估流程
"""

import pytest
from unittest.mock import AsyncMock

from core.types import ToolCall
from evaluation.tool_accuracy import ToolCallEvaluator


class TestToolAccuracyIntegration:
    """工具调用准确率集成测试"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器"""
        return ToolCallEvaluator()

    @pytest.fixture
    def mock_agent_response(self):
        """Mock Agent 响应"""
        response = AsyncMock()
        response.tool_calls = [
            ToolCall(
                id="call_1",
                name="read_file",
                arguments={"path": "/tmp/test.txt"},
            ),
        ]
        return response

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

        # Act
        result = evaluator.evaluate_tool_sequence(
            task_id="file_operation_task",
            actual_tool_calls=tool_calls,
            expected_tools=["read_file", "write_file"],
            expected_sequence=["read_file", "write_file"],
            tool_expectations={
                "read_file": {
                    "params": {"path": "/tmp/input.txt"},
                },
                "write_file": {
                    "params": {"path": "/tmp/output.txt"},
                },
            },
        )

        # Assert
        assert result.overall_score >= 0.8
        assert len(result.missing_tools) == 0
        assert result.sequence_score >= 0.9

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

        # Act
        result = evaluator.evaluate_tool_sequence(
            task_id="incomplete_task",
            actual_tool_calls=tool_calls,
            required_tools=["read_file", "write_file", "delete_file"],
        )

        # Assert
        assert len(result.missing_tools) > 0
        assert "write_file" in result.missing_tools or "delete_file" in result.missing_tools
        assert result.overall_score < 0.7

    def test_evaluate_wrong_tool_selection(self, evaluator):
        """测试: 评估工具选择错误"""
        # Arrange - 使用了错误的工具
        tool_calls = [
            ToolCall(
                id="call_1",
                name="write_file",
                arguments={"path": "/tmp/test.txt", "content": "data"},
            ),
        ]

        # Act
        result = evaluator.evaluate_tool_sequence(
            task_id="wrong_tool_task",
            actual_tool_calls=tool_calls,
            expected_tools=["read_file"],
            tool_expectations={
                "read_file": {
                    "params": {"path": "/tmp/test.txt"},
                },
            },
        )

        # Assert
        assert len(result.unnecessary_tools) > 0
        assert result.tool_scores[0].accuracy == "wrong_tool"
        assert result.overall_score < 0.5

    def test_evaluate_parameter_accuracy(self, evaluator):
        """测试: 评估参数准确性"""
        # Arrange - 参数部分正确
        tool_calls = [
            ToolCall(
                id="call_1",
                name="read_file",
                arguments={"path": "/tmp/test.txt", "encoding": "utf-8"},
            ),
        ]

        # Act
        result = evaluator.evaluate_tool_sequence(
            task_id="param_test_task",
            actual_tool_calls=tool_calls,
            tool_expectations={
                "read_file": {
                    "params": {"path": "/tmp/test.txt", "encoding": "utf-8", "offset": 0},
                },
            },
        )

        # Assert
        assert result.tool_scores[0].score < 1.0
        assert result.tool_scores[0].accuracy == "wrong_params"

    def test_generate_comprehensive_report(self, evaluator):
        """测试: 生成综合评估报告"""
        # Arrange - 多个任务
        tasks = [
            {
                "task_id": "task_1",
                "tool_calls": [
                    ToolCall(id="c1", name="read_file", arguments={"path": "/tmp/a.txt"}),
                ],
                "expected_tools": ["read_file"],
            },
            {
                "task_id": "task_2",
                "tool_calls": [
                    ToolCall(id="c2", name="write_file", arguments={"path": "/tmp/b.txt"}),
                ],
                "expected_tools": ["write_file"],
            },
        ]

        # Act
        for task in tasks:
            evaluator.evaluate_tool_sequence(
                task_id=task["task_id"],
                actual_tool_calls=task["tool_calls"],
                expected_tools=task["expected_tools"],
            )

        report = evaluator.generate_report()

        # Assert
        assert report["total_tasks"] == 2
        assert "average_score" in report
        assert "tool_accuracy_breakdown" in report
        assert "read_file" in report["tool_accuracy_breakdown"]
        assert "write_file" in report["tool_accuracy_breakdown"]
