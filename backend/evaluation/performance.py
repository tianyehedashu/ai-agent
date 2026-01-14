"""
性能评估

评估 Agent 的性能指标（延迟、吞吐量、资源使用）
"""

import asyncio
from dataclasses import dataclass
import statistics
import time
from typing import Any


@dataclass
class PerformanceMetrics:
    """性能指标"""

    # 延迟指标 (ms)
    latency_p50: float
    latency_p90: float
    latency_p99: float
    latency_avg: float
    latency_min: float
    latency_max: float

    # 吞吐量
    requests_per_second: float

    # Token 指标
    tokens_per_second: float
    avg_tokens_per_request: float

    # 资源使用
    avg_memory_mb: float = 0.0
    peak_memory_mb: float = 0.0
    avg_cpu_percent: float = 0.0


class PerformanceEvaluator:
    """性能评估器"""

    def __init__(self, agent: Any, num_requests: int = 100, concurrency: int = 10):
        self.agent = agent
        self.num_requests = num_requests
        self.concurrency = concurrency
        self.results: list[dict[str, Any]] = []

    async def run_benchmark(self, test_prompts: list[str]) -> PerformanceMetrics:
        """运行性能基准测试"""
        # 准备请求
        prompts = test_prompts * (self.num_requests // len(test_prompts) + 1)
        prompts = prompts[: self.num_requests]

        # 并发执行
        semaphore = asyncio.Semaphore(self.concurrency)

        async def bounded_request(prompt: str) -> dict[str, Any]:
            async with semaphore:
                return await self._single_request(prompt)

        start_time = time.time()

        tasks = [bounded_request(p) for p in prompts]
        self.results = await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        return self._calculate_metrics(total_time)

    async def _single_request(self, prompt: str) -> dict[str, Any]:
        """执行单个请求"""
        start = time.time()

        try:
            response = await self.agent.run(prompt)

            return {
                "success": True,
                "latency_ms": (time.time() - start) * 1000,
                "tokens": getattr(response, "total_tokens", 0),
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "latency_ms": (time.time() - start) * 1000,
                "tokens": 0,
                "error": str(e),
            }

    def _calculate_metrics(self, total_time: float) -> PerformanceMetrics:
        """计算性能指标"""
        latencies = [r["latency_ms"] for r in self.results if r["success"]]
        tokens = [r["tokens"] for r in self.results if r["success"]]

        latencies.sort()

        def percentile(data: list[float], p: float) -> float:
            if not data:
                return 0.0
            k = (len(data) - 1) * p / 100
            f = int(k)
            c = f + 1 if f + 1 < len(data) else f
            return data[f] + (k - f) * (data[c] - data[f])

        return PerformanceMetrics(
            latency_p50=percentile(latencies, 50),
            latency_p90=percentile(latencies, 90),
            latency_p99=percentile(latencies, 99),
            latency_avg=statistics.mean(latencies) if latencies else 0.0,
            latency_min=min(latencies) if latencies else 0.0,
            latency_max=max(latencies) if latencies else 0.0,
            requests_per_second=len(self.results) / total_time if total_time > 0 else 0.0,
            tokens_per_second=sum(tokens) / total_time if total_time > 0 else 0.0,
            avg_tokens_per_request=statistics.mean(tokens) if tokens else 0.0,
        )


class LoadTestRunner:
    """负载测试运行器"""

    async def run_load_test(
        self,
        agent: Any,
        prompts: list[str],
        duration_seconds: int = 60,
        target_rps: float = 10,
    ) -> dict[str, Any]:
        """
        运行负载测试

        Args:
            agent: Agent 实例
            prompts: 测试提示词
            duration_seconds: 测试持续时间
            target_rps: 目标每秒请求数

        Returns:
            负载测试结果
        """
        import random

        start_time = time.time()
        request_interval = 1.0 / target_rps

        async def timed_request(prompt: str) -> dict[str, Any]:
            req_start = time.time()
            try:
                response = await agent.run(prompt)
                return {
                    "success": True,
                    "latency_ms": (time.time() - req_start) * 1000,
                    "tokens": getattr(response, "total_tokens", 0),
                }
            except Exception as e:
                return {
                    "success": False,
                    "latency_ms": (time.time() - req_start) * 1000,
                    "tokens": 0,
                    "error": str(e),
                }

        tasks: list[asyncio.Task] = []

        while time.time() - start_time < duration_seconds:
            prompt = random.choice(prompts)
            task = asyncio.create_task(timed_request(prompt))
            tasks.append(task)

            await asyncio.sleep(request_interval)

        # 等待所有请求完成
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        return self._analyze_load_test(completed, duration_seconds, target_rps)

    def _analyze_load_test(
        self,
        completed: list[Any],
        duration_seconds: int,
        target_rps: float,
    ) -> dict[str, Any]:
        """分析负载测试结果"""
        results = [r for r in completed if isinstance(r, dict)]
        successful = [r for r in results if r.get("success", False)]

        return {
            "total_requests": len(results),
            "successful_requests": len(successful),
            "success_rate": len(successful) / len(results) if results else 0.0,
            "actual_rps": len(results) / duration_seconds if duration_seconds > 0 else 0.0,
            "target_rps": target_rps,
            "avg_latency_ms": (
                statistics.mean([r["latency_ms"] for r in successful]) if successful else 0.0
            ),
        }
