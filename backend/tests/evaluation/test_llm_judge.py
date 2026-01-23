"""
LLM-as-Judge 测试

测试 LLM 评估功能
"""

from unittest.mock import AsyncMock

import pytest

from shared.infrastructure.llm.gateway import LLMResponse
from evaluation.llm_judge import LLMJudge, MultiDimensionJudge


class TestLLMJudge:
    """LLM-as-Judge 测试"""

    @pytest.fixture
    def mock_llm_gateway(self):
        """Mock LLM Gateway"""
        gateway = AsyncMock()
        gateway.chat = AsyncMock()
        return gateway

    @pytest.fixture
    def judge(self, mock_llm_gateway):
        """创建评估器"""
        return LLMJudge(llm_gateway=mock_llm_gateway, judge_model="gpt-4")

    @pytest.mark.asyncio
    async def test_evaluate_response(self, judge, mock_llm_gateway):
        """测试: 评估响应"""
        # Arrange
        mock_response = LLMResponse(
            content='{"overall_score": 8.5, "relevance": 9, "accuracy": 8, "completeness": 8, "clarity": 9, "reasoning": "Good response"}',
        )
        mock_llm_gateway.chat.return_value = mock_response

        # Act
        score = await judge.evaluate(
            query="What is Python?",
            response="Python is a programming language.",
        )

        # Assert
        assert score.overall_score > 0
        assert score.relevance > 0
        assert score.accuracy > 0
        mock_llm_gateway.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_with_expected_output(self, judge, mock_llm_gateway):
        """测试: 带期望输出的评估"""
        # Arrange
        mock_response = LLMResponse(
            content='{"overall_score": 9.0, "relevance": 9, "accuracy": 9, "completeness": 9, "clarity": 9, "reasoning": "Matches expected"}',
        )
        mock_llm_gateway.chat.return_value = mock_response

        # Act
        score = await judge.evaluate(
            query="What is 2+2?",
            response="4",
            expected="4",
        )

        # Assert
        assert score.overall_score >= 0
        assert len(score.reasoning) > 0

    @pytest.mark.asyncio
    async def test_compare_responses(self, judge, mock_llm_gateway):
        """测试: 对比两个响应"""
        # Arrange
        mock_response = LLMResponse(
            content='{"winner": "A", "score_a": 8.5, "score_b": 7.0, "reasoning": "Response A is better"}',
        )
        mock_llm_gateway.chat.return_value = mock_response

        # Act
        comparison = await judge.compare(
            query="What is Python?",
            response_a="Python is a programming language.",
            response_b="Python is a snake.",
        )

        # Assert
        assert "winner" in comparison
        assert "score_a" in comparison
        assert "score_b" in comparison
        assert comparison["score_a"] > comparison["score_b"]

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, judge, mock_llm_gateway):
        """测试: 处理无效 JSON"""
        # Arrange
        mock_response = LLMResponse(content="Invalid JSON response")
        mock_llm_gateway.chat.return_value = mock_response

        # Act
        score = await judge.evaluate(
            query="Test",
            response="Test response",
        )

        # Assert
        # 应该返回默认值而不是崩溃
        assert score.overall_score == 5.0
        assert "Failed to parse" in score.reasoning


class TestMultiDimensionJudge:
    """多维度评估器测试"""

    @pytest.fixture
    def mock_llm_gateway(self):
        """Mock LLM Gateway"""
        gateway = AsyncMock()
        gateway.chat = AsyncMock()
        return gateway

    @pytest.fixture
    def judge(self, mock_llm_gateway):
        """创建评估器"""
        return MultiDimensionJudge(llm_gateway=mock_llm_gateway, judge_model="gpt-4")

    @pytest.mark.asyncio
    async def test_evaluate_all_dimensions(self, judge, mock_llm_gateway):
        """测试: 评估所有维度"""
        # Arrange
        mock_response = LLMResponse(content="8.5")
        mock_llm_gateway.chat.return_value = mock_response

        # Act
        scores = await judge.evaluate_all_dimensions(
            query="What is Python?",
            response="Python is a programming language.",
        )

        # Assert
        assert "helpfulness" in scores
        assert "harmlessness" in scores
        assert "honesty" in scores
        assert "factuality" in scores
        assert "coherence" in scores
        assert "overall" in scores
        assert all(0 <= score <= 10 for score in scores.values())
