"""
任务完成率评估

评估 Agent 完成指定任务的能力
"""

from dataclasses import dataclass
from enum import Enum
import time
from typing import Any

from pydantic import BaseModel


class TaskStatus(str, Enum):
    """任务状态"""

    SUCCESS = "success"  # 完全成功
    PARTIAL = "partial"  # 部分成功
    FAILED = "failed"  # 失败
    TIMEOUT = "timeout"  # 超时
    ERROR = "error"  # 错误


@dataclass
class TaskEvalResult:
    """任务评估结果"""

    task_id: str
    status: TaskStatus
    score: float  # 0.0 - 1.0
    expected_output: str | None
    actual_output: str
    steps_taken: int
    time_taken_ms: int
    tokens_used: int
    errors: list[str]
    metadata: dict[str, Any]


class EvaluationReport(BaseModel):
    """评估报告"""

    total_tasks: int
    success_count: int
    partial_count: int
    failed_count: int
    success_rate: float
    average_score: float
    average_time_ms: float
    average_tokens: float
    results: list[TaskEvalResult]


class TaskEvaluator:
    """任务完成率评估器"""

    def __init__(self, test_cases: list[dict[str, Any]]):
        self.test_cases = test_cases
        self.results: list[TaskEvalResult] = []

    async def run_evaluation(self, agent: Any) -> EvaluationReport:
        """运行评估"""
        for case in self.test_cases:
            result = await self._evaluate_single(agent, case)
            self.results.append(result)

        return self._generate_report()

    async def _evaluate_single(self, agent: Any, case: dict[str, Any]) -> TaskEvalResult:
        """评估单个测试用例"""
        task_id = case["id"]
        input_prompt = case["input"]
        expected = case.get("expected_output")
        criteria = case.get("criteria", {})
        timeout = case.get("timeout", 60)

        start_time = time.time()

        try:
            # 执行 Agent
            response = await agent.run(input_prompt, timeout=timeout)

            # 评估输出
            score = await self._score_output(
                expected=expected,
                actual=response.content if hasattr(response, "content") else str(response),
                criteria=criteria,
            )

            status = self._determine_status(score, response)

            return TaskEvalResult(
                task_id=task_id,
                status=status,
                score=score,
                expected_output=expected,
                actual_output=response.content if hasattr(response, "content") else str(response),
                steps_taken=getattr(response, "iterations", 0),
                time_taken_ms=int((time.time() - start_time) * 1000),
                tokens_used=getattr(response, "total_tokens", 0),
                errors=[],
                metadata={"criteria": criteria},
            )

        except TimeoutError:
            return TaskEvalResult(
                task_id=task_id,
                status=TaskStatus.TIMEOUT,
                score=0.0,
                expected_output=expected,
                actual_output="",
                steps_taken=0,
                time_taken_ms=int((time.time() - start_time) * 1000),
                tokens_used=0,
                errors=["Timeout"],
                metadata={},
            )
        except Exception as e:
            return TaskEvalResult(
                task_id=task_id,
                status=TaskStatus.ERROR,
                score=0.0,
                expected_output=expected,
                actual_output="",
                steps_taken=0,
                time_taken_ms=int((time.time() - start_time) * 1000),
                tokens_used=0,
                errors=[str(e)],
                metadata={},
            )

    async def _score_output(
        self,
        expected: str | None,
        actual: str,
        criteria: dict[str, Any],
    ) -> float:
        """评估输出得分"""
        if expected is None:
            # 使用 LLM-as-Judge 或其他评估方法
            return await self._score_with_criteria(actual, criteria)

        # 精确匹配
        if criteria.get("exact_match", False):
            return 1.0 if actual.strip() == expected.strip() else 0.0

        # 包含关键词
        if keywords := criteria.get("contains_keywords"):
            score = 0.0
            for keyword in keywords:
                if keyword.lower() in actual.lower():
                    score += 1.0 / len(keywords)
            return score

        # 模糊匹配（简单实现）
        expected_lower = expected.lower()
        actual_lower = actual.lower()
        if expected_lower in actual_lower or actual_lower in expected_lower:
            return 0.8

        return 0.0

    async def _score_with_criteria(self, actual: str, criteria: dict[str, Any]) -> float:
        """使用标准评估输出"""
        score = 1.0

        # 检查长度限制
        if (max_length := criteria.get("max_length")) and len(actual) > max_length:
            score *= 0.8

        # 检查必须包含的关键词
        if keywords := criteria.get("contains_keywords"):
            for keyword in keywords:
                if keyword.lower() not in actual.lower():
                    score *= 0.7

        return score

    def _determine_status(self, score: float, response: Any) -> TaskStatus:
        """确定任务状态"""
        if score >= 0.9:
            return TaskStatus.SUCCESS
        elif score >= 0.5:
            return TaskStatus.PARTIAL
        else:
            return TaskStatus.FAILED

    def _generate_report(self) -> EvaluationReport:
        """生成评估报告"""
        total = len(self.results)
        success = sum(1 for r in self.results if r.status == TaskStatus.SUCCESS)
        partial = sum(1 for r in self.results if r.status == TaskStatus.PARTIAL)
        failed = sum(1 for r in self.results if r.status == TaskStatus.FAILED)

        return EvaluationReport(
            total_tasks=total,
            success_count=success,
            partial_count=partial,
            failed_count=failed,
            success_rate=success / total if total > 0 else 0,
            average_score=sum(r.score for r in self.results) / total if total > 0 else 0,
            average_time_ms=sum(r.time_taken_ms for r in self.results) / total if total > 0 else 0,
            average_tokens=sum(r.tokens_used for r in self.results) / total if total > 0 else 0,
            results=self.results,
        )
