"""
任务评估器测试

测试任务完成率评估功能
"""

import pytest

from evaluation.task_completion import TaskEvaluator, TaskStatus


class MockAgent:
    """Mock Agent 用于测试"""

    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.call_count = 0

    async def run(self, prompt: str, timeout: int = 60):
        """模拟 Agent 运行"""
        self.call_count += 1
        response = self.responses.get(
            prompt, {"content": "Default response", "iterations": 1, "total_tokens": 100}
        )
        return type("Response", (), response)()


class TestTaskEvaluator:
    """任务评估器测试"""

    @pytest.fixture
    def simple_test_cases(self):
        """简单测试用例"""
        return [
            {
                "id": "test_001",
                "input": "What is 2 + 2?",
                "expected_output": "4",
                "criteria": {"exact_match": True},
            },
            {
                "id": "test_002",
                "input": "Say hello",
                "expected_output": "Hello",
                "criteria": {"exact_match": False},
            },
        ]

    @pytest.fixture
    def mock_agent(self):
        """Mock Agent"""
        responses = {
            "What is 2 + 2?": {
                "content": "4",
                "iterations": 1,
                "total_tokens": 50,
            },
            "Say hello": {
                "content": "Hello, how can I help?",
                "iterations": 1,
                "total_tokens": 30,
            },
        }
        return MockAgent(responses)

    @pytest.mark.asyncio
    async def test_run_evaluation(self, simple_test_cases, mock_agent):
        """测试: 运行评估"""
        # Arrange
        evaluator = TaskEvaluator(simple_test_cases)

        # Act
        report = await evaluator.run_evaluation(mock_agent)

        # Assert
        assert report.total_tasks == 2
        assert len(report.results) == 2
        assert mock_agent.call_count == 2

    @pytest.mark.asyncio
    async def test_evaluate_exact_match(self, mock_agent):
        """测试: 精确匹配评估"""
        # Arrange
        test_cases = [
            {
                "id": "exact_001",
                "input": "What is 2 + 2?",
                "expected_output": "4",
                "criteria": {"exact_match": True},
            },
        ]
        evaluator = TaskEvaluator(test_cases)

        # Act
        report = await evaluator.run_evaluation(mock_agent)

        # Assert
        result = report.results[0]
        assert result.status == TaskStatus.SUCCESS
        assert result.score >= 0.9

    @pytest.mark.asyncio
    async def test_evaluate_keywords_match(self, mock_agent):
        """测试: 关键词匹配评估"""
        # Arrange
        test_cases = [
            {
                "id": "keyword_001",
                "input": "Say hello",
                "expected_output": None,
                "criteria": {"contains_keywords": ["hello", "greeting"]},
            },
        ]
        evaluator = TaskEvaluator(test_cases)

        # Act
        report = await evaluator.run_evaluation(mock_agent)

        # Assert
        result = report.results[0]
        assert result.score > 0

    @pytest.mark.asyncio
    async def test_evaluate_timeout(self, mock_agent):
        """测试: 超时处理"""

        # Arrange
        async def slow_run(prompt: str, timeout: int = 60):
            import asyncio

            await asyncio.sleep(timeout + 1)
            return type(
                "Response", (), {"content": "Too late", "iterations": 0, "total_tokens": 0}
            )()

        mock_agent.run = slow_run
        test_cases = [
            {
                "id": "timeout_001",
                "input": "Slow task",
                "expected_output": "Result",
                "criteria": {},
                "timeout": 1,
            },
        ]
        evaluator = TaskEvaluator(test_cases)

        # Act
        report = await evaluator.run_evaluation(mock_agent)

        # Assert
        result = report.results[0]
        assert result.status == TaskStatus.TIMEOUT
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_error_handling(self, mock_agent):
        """测试: 错误处理"""

        # Arrange
        async def failing_run(prompt: str, timeout: int = 60):
            raise Exception("Agent execution failed")  # pylint: disable=broad-exception-raised

        mock_agent.run = failing_run
        test_cases = [
            {
                "id": "error_001",
                "input": "Failing task",
                "expected_output": "Result",
                "criteria": {},
            },
        ]
        evaluator = TaskEvaluator(test_cases)

        # Act
        report = await evaluator.run_evaluation(mock_agent)

        # Assert
        result = report.results[0]
        assert result.status == TaskStatus.ERROR
        assert result.score == 0.0
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_generate_report(self, simple_test_cases, mock_agent):
        """测试: 生成报告"""
        # Arrange
        evaluator = TaskEvaluator(simple_test_cases)

        # Act
        report = await evaluator.run_evaluation(mock_agent)

        # Assert
        assert report.total_tasks == 2
        assert report.success_count >= 0
        assert report.partial_count >= 0
        assert report.failed_count >= 0
        assert 0 <= report.success_rate <= 1
        assert 0 <= report.average_score <= 1
        assert report.average_time_ms > 0
