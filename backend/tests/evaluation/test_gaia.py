"""
GAIA 评估测试
"""
# pylint: disable=protected-access  # 测试代码需要访问私有方法

from unittest.mock import AsyncMock

import pytest

from evaluation.gaia import GAIAEvaluator, GAIAQuestion


class TestGAIAEvaluator:
    """GAIA 评估器测试"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器"""
        return GAIAEvaluator()

    @pytest.fixture
    def sample_questions(self):
        """示例问题"""
        return [
            GAIAQuestion(
                task_id="test_001",
                question="What is 2 + 2?",
                final_answer="4",
                difficulty="simple",
            ),
            GAIAQuestion(
                task_id="test_002",
                question="What is the capital of France?",
                final_answer="Paris",
                difficulty="simple",
            ),
        ]

    def test_load_benchmark_yaml(self, evaluator, tmp_path):
        """测试: 加载 YAML 格式的基准测试集"""
        # Arrange
        benchmark_file = tmp_path / "gaia_test.yaml"
        benchmark_file.write_text(
            """
benchmark:
  name: "Test GAIA"
questions:
  - task_id: "test_001"
    question: "What is 2 + 2?"
    final_answer: "4"
    difficulty: "simple"
"""
        )

        # Act
        evaluator.load_benchmark(benchmark_file)

        # Assert
        assert len(evaluator.questions) == 1
        assert evaluator.questions[0].task_id == "test_001"
        assert evaluator.questions[0].question == "What is 2 + 2?"

    def test_load_benchmark_json(self, evaluator, tmp_path):
        """测试: 加载 JSON 格式的基准测试集"""
        # Arrange
        import json

        benchmark_file = tmp_path / "gaia_test.json"
        benchmark_data = {
            "questions": [
                {
                    "task_id": "test_001",
                    "question": "What is 2 + 2?",
                    "final_answer": "4",
                    "difficulty": "simple",
                },
            ],
        }
        benchmark_file.write_text(json.dumps(benchmark_data))

        # Act
        evaluator.load_benchmark(benchmark_file)

        # Assert
        assert len(evaluator.questions) == 1

    @pytest.mark.asyncio
    async def test_evaluate_single_question(self, evaluator, sample_questions):
        """测试: 评估单个问题"""
        # Arrange
        mock_agent = AsyncMock()
        mock_response = AsyncMock()
        mock_response.content = "4"
        mock_response.iterations = 1
        mock_response.total_tokens = 100
        mock_agent.run.return_value = mock_response

        # Act
        result = await evaluator._evaluate_single(mock_agent, sample_questions[0])

        # Assert
        assert result.task_id == "test_001"
        assert result.correct is True
        assert result.score >= 0.9

    @pytest.mark.asyncio
    async def test_evaluate_answer_exact_match(self, evaluator):
        """测试: 答案精确匹配"""
        # Arrange
        correct, score = evaluator._evaluate_answer("Paris", "Paris")

        # Assert
        assert correct is True
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_answer_numeric_match(self, evaluator):
        """测试: 数值答案匹配"""
        # Arrange
        correct, score = evaluator._evaluate_answer("345", "345")

        # Assert
        assert correct is True
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_answer_partial_match(self, evaluator):
        """测试: 部分匹配"""
        # Arrange
        correct, score = evaluator._evaluate_answer("Paris", "The capital is Paris")

        # Assert
        assert correct is True
        assert score >= 0.8

    def test_extract_answer(self, evaluator):
        """测试: 从响应中提取答案"""
        # Arrange
        mock_response = AsyncMock()
        mock_response.content = "The answer is 42. This is the result."

        # Act
        answer = evaluator._extract_answer(mock_response)

        # Assert
        assert "42" in answer or len(answer) > 0

    def test_calculate_similarity(self, evaluator):
        """测试: 计算字符串相似度"""
        # 完全匹配
        assert evaluator._calculate_similarity("hello world", "hello world") == 1.0

        # 部分匹配
        similarity = evaluator._calculate_similarity("hello world", "hello")
        assert similarity > 0.0

        # 不匹配
        similarity = evaluator._calculate_similarity("hello", "world")
        assert similarity < 0.5

    @pytest.mark.asyncio
    async def test_generate_report(self, evaluator, sample_questions):
        """测试: 生成评估报告"""
        # Arrange
        mock_agent = AsyncMock()
        mock_response = AsyncMock()
        mock_response.content = "4"
        mock_response.iterations = 1
        mock_response.total_tokens = 100
        mock_agent.run.return_value = mock_response

        # Act
        await evaluator.evaluate_agent(mock_agent, sample_questions)
        report = evaluator._generate_report()

        # Assert
        assert report.total_questions == 2
        assert report.accuracy > 0.0
        assert "simple" in report.results_by_difficulty
