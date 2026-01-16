"""
性能评估测试
"""

import asyncio

import pytest

from evaluation.performance import LoadTestRunner, PerformanceEvaluator


class MockAgent:
    """Mock Agent 用于性能测试"""

    def __init__(self, latency_ms: float = 100, tokens: int = 100):
        self.latency_ms = latency_ms
        self.tokens = tokens

    async def run(self, prompt: str):
        """模拟 Agent 运行"""
        await asyncio.sleep(self.latency_ms / 1000)
        return type("Response", (), {"total_tokens": self.tokens})()


class TestPerformanceEvaluator:
    """性能评估器测试"""

    @pytest.fixture
    def mock_agent(self):
        """Mock Agent"""
        return MockAgent(latency_ms=50, tokens=100)

    @pytest.fixture
    def test_prompts(self):
        """测试提示词"""
        return ["Test prompt 1", "Test prompt 2", "Test prompt 3"]

    @pytest.mark.asyncio
    async def test_run_benchmark(self, mock_agent, test_prompts):
        """测试: 运行性能基准测试"""
        # Arrange
        evaluator = PerformanceEvaluator(mock_agent, num_requests=10, concurrency=5)

        # Act
        metrics = await evaluator.run_benchmark(test_prompts)

        # Assert
        assert metrics.latency_avg > 0
        assert metrics.requests_per_second > 0
        assert metrics.avg_tokens_per_request > 0
        assert metrics.latency_p50 <= metrics.latency_p90 <= metrics.latency_p99

    @pytest.mark.asyncio
    async def test_calculate_percentiles(self, mock_agent, test_prompts):
        """测试: 计算百分位数"""
        # Arrange
        evaluator = PerformanceEvaluator(mock_agent, num_requests=20, concurrency=5)

        # Act
        metrics = await evaluator.run_benchmark(test_prompts)

        # Assert
        assert metrics.latency_p50 > 0
        assert metrics.latency_p90 >= metrics.latency_p50
        assert metrics.latency_p99 >= metrics.latency_p90
        assert metrics.latency_min <= metrics.latency_avg <= metrics.latency_max

    @pytest.mark.asyncio
    async def test_handle_failures(self):
        """测试: 处理失败请求"""

        # Arrange
        async def failing_agent(prompt: str):
            raise Exception("Agent failed")

        agent = type("Agent", (), {"run": failing_agent})()
        evaluator = PerformanceEvaluator(agent, num_requests=5, concurrency=2)

        # Act
        metrics = await evaluator.run_benchmark(["test"])

        # Assert
        # 应该仍然计算指标，但成功率为 0
        assert metrics.latency_avg >= 0


class TestLoadTestRunner:
    """负载测试运行器测试"""

    @pytest.fixture
    def mock_agent(self):
        """Mock Agent"""
        return MockAgent(latency_ms=10, tokens=50)

    @pytest.mark.asyncio
    async def test_run_load_test(self, mock_agent):
        """测试: 运行负载测试"""
        # Arrange
        runner = LoadTestRunner()
        prompts = ["Test prompt"]

        # Act
        result = await runner.run_load_test(
            agent=mock_agent,
            prompts=prompts,
            duration_seconds=2,
            target_rps=5,
        )

        # Assert
        assert result["total_requests"] > 0
        assert "success_rate" in result
        assert "actual_rps" in result
        assert result["target_rps"] == 5

    @pytest.mark.asyncio
    async def test_load_test_metrics(self, mock_agent):
        """测试: 负载测试指标"""
        # Arrange
        runner = LoadTestRunner()
        prompts = ["Test prompt 1", "Test prompt 2"]

        # Act
        result = await runner.run_load_test(
            agent=mock_agent,
            prompts=prompts,
            duration_seconds=3,
            target_rps=10,
        )

        # Assert
        assert result["successful_requests"] >= 0
        assert 0 <= result["success_rate"] <= 1
        assert result["avg_latency_ms"] >= 0
