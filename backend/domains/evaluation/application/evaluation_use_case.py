"""Evaluation application layer — orchestrates benchmarks without presentation → infrastructure."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bootstrap.config import settings
from domains.agent.domain.types import ToolCall
from domains.agent.infrastructure.llm.agent_llm_facade import AgentLlmFacade

if TYPE_CHECKING:
    from pathlib import Path

    from evaluation.gaia import GAIAEvaluator
    from evaluation.llm_judge import JudgeScore, LLMJudge
    from evaluation.task_completion import EvaluationReport
    from evaluation.tool_accuracy import ToolAccuracyEvaluator, ToolAccuracyReport


class EvaluationUseCase:
    """评估用例：封装对 LLM 与 benchmark 库的调用。"""

    def __init__(self) -> None:
        self._llm = AgentLlmFacade(config=settings)

    @property
    def llm_gateway(self) -> AgentLlmFacade:
        return self._llm

    def tool_accuracy_evaluator(self) -> ToolAccuracyEvaluator:
        from evaluation.tool_accuracy import ToolAccuracyEvaluator

        return ToolAccuracyEvaluator()

    def gaia_evaluator(self, benchmark_path: Path) -> GAIAEvaluator:
        from evaluation.gaia import GAIAEvaluator

        evaluator = GAIAEvaluator(benchmark_path)
        evaluator.load_benchmark(benchmark_path)
        return evaluator

    def llm_judge(self) -> LLMJudge:
        from evaluation.llm_judge import LLMJudge

        return LLMJudge(self._llm)

    async def run_tool_accuracy(
        self,
        tool_calls: list[dict[str, Any]],
        expected_tools: dict[str, str] | None = None,
        expected_args: dict[str, dict[str, Any]] | None = None,
    ) -> ToolAccuracyReport:
        parsed = [ToolCall.model_validate(tc) for tc in tool_calls]
        evaluator = self.tool_accuracy_evaluator()
        for tool_call in parsed:
            expected_tool = expected_tools.get(tool_call.id) if expected_tools else None
            expected_arg = expected_args.get(tool_call.id) if expected_args else None
            evaluator.evaluate_tool_call(
                tool_call=tool_call,
                expected_tool=expected_tool,
                expected_args=expected_arg,
            )
        return evaluator.generate_report()

    async def run_llm_judge(
        self,
        *,
        query: str,
        response: str,
        expected: str | None = None,
        criteria: dict[str, Any] | None = None,
        judge_model: str | None = None,
    ) -> JudgeScore:
        judge = self.llm_judge()
        if judge_model is not None:
            judge.judge_model = judge_model
        return await judge.evaluate(
            query=query,
            response=response,
            expected=expected,
            criteria=criteria,
        )

    async def run_task_completion(
        self,
        test_cases: list[dict[str, Any]],
        agent: Any,
    ) -> EvaluationReport:
        from evaluation.task_completion import TaskEvaluator

        evaluator = TaskEvaluator(test_cases)
        return await evaluator.run_evaluation(agent)


__all__ = ["EvaluationUseCase"]
