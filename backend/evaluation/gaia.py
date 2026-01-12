"""
GAIA 评估基准集成

GAIA (General AI Assistant) 是一个真实世界的 AI Agent 评估基准
包含需要多步骤推理、工具使用和真实世界知识的任务
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from evaluation.task_completion import TaskEvaluator, TaskEvalResult, TaskStatus


class GAIAQuestion(BaseModel):
    """GAIA 问题"""

    task_id: str
    question: str
    final_answer: str
    file_paths: list[str] | None = None
    annotations: dict[str, Any] | None = None
    difficulty: str | None = None  # "simple", "medium", "hard"


class GAIAResult(BaseModel):
    """GAIA 评估结果"""

    task_id: str
    question: str
    expected_answer: str
    actual_answer: str
    correct: bool
    score: float  # 0.0 - 1.0
    time_taken_ms: int
    steps_taken: int
    tokens_used: int
    tool_calls_count: int
    metadata: dict[str, Any]


class GAIAReport(BaseModel):
    """GAIA 评估报告"""

    total_questions: int
    correct_count: int
    accuracy: float
    average_score: float
    average_time_ms: float
    average_steps: float
    average_tokens: float
    average_tool_calls: float
    results_by_difficulty: dict[str, dict[str, float]]
    results: list[GAIAResult]


class GAIAEvaluator:
    """GAIA 评估器"""

    def __init__(self, benchmark_path: str | Path | None = None):
        self.benchmark_path = Path(benchmark_path) if benchmark_path else None
        self.questions: list[GAIAQuestion] = []
        self.results: list[GAIAResult] = []

    def load_benchmark(self, path: str | Path | None = None):
        """加载 GAIA 基准测试集"""
        path = Path(path) if path else self.benchmark_path
        if not path or not path.exists():
            raise FileNotFoundError(f"GAIA benchmark not found: {path}")

        # 支持 JSON 和 YAML 格式
        if path.suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif path.suffix in [".yaml", ".yml"]:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

        # 解析问题
        questions_data = data.get("questions", data.get("test_cases", []))
        for q_data in questions_data:
            question = GAIAQuestion(
                task_id=q_data.get("task_id", q_data.get("id", "")),
                question=q_data.get("question", q_data.get("input", "")),
                final_answer=q_data.get("final_answer", q_data.get("expected_output", "")),
                file_paths=q_data.get("file_paths"),
                annotations=q_data.get("annotations"),
                difficulty=q_data.get("difficulty"),
            )
            self.questions.append(question)

    async def evaluate_agent(
        self,
        agent: Any,
        questions: list[GAIAQuestion] | None = None,
    ) -> GAIAReport:
        """评估 Agent 在 GAIA 基准上的表现"""
        questions = questions or self.questions

        if not questions:
            raise ValueError("No questions to evaluate")

        for question in questions:
            result = await self._evaluate_single(agent, question)
            self.results.append(result)

        return self._generate_report()

    async def _evaluate_single(
        self,
        agent: Any,
        question: GAIAQuestion,
    ) -> GAIAResult:
        """评估单个问题"""
        start_time = time.time()

        try:
            # 执行 Agent
            response = await agent.run(question.question, timeout=300)

            # 提取答案
            actual_answer = self._extract_answer(response)

            # 评估答案正确性
            correct, score = self._evaluate_answer(
                expected=question.final_answer,
                actual=actual_answer,
            )

            # 统计信息
            steps_taken = getattr(response, "iterations", 0)
            tokens_used = getattr(response, "total_tokens", 0)
            tool_calls = self._count_tool_calls(response)

            return GAIAResult(
                task_id=question.task_id,
                question=question.question,
                expected_answer=question.final_answer,
                actual_answer=actual_answer,
                correct=correct,
                score=score,
                time_taken_ms=int((time.time() - start_time) * 1000),
                steps_taken=steps_taken,
                tokens_used=tokens_used,
                tool_calls_count=tool_calls,
                metadata={
                    "difficulty": question.difficulty,
                    "file_paths": question.file_paths,
                },
            )

        except Exception as e:
            return GAIAResult(
                task_id=question.task_id,
                question=question.question,
                expected_answer=question.final_answer,
                actual_answer="",
                correct=False,
                score=0.0,
                time_taken_ms=int((time.time() - start_time) * 1000),
                steps_taken=0,
                tokens_used=0,
                tool_calls_count=0,
                metadata={"error": str(e)},
            )

    def _extract_answer(self, response: Any) -> str:
        """从响应中提取答案"""
        if hasattr(response, "content"):
            content = response.content
        else:
            content = str(response)

        # 尝试提取最终答案（通常在最后）
        # GAIA 答案通常是简洁的
        lines = content.strip().split("\n")
        if lines:
            # 取最后一行或包含数字/关键信息的一行
            for line in reversed(lines):
                line = line.strip()
                if line and len(line) < 200:  # 答案通常较短
                    return line

        return content.strip()[:200]  # 截取前200字符

    def _evaluate_answer(self, expected: str, actual: str) -> tuple[bool, float]:
        """评估答案正确性"""
        expected_clean = expected.strip().lower()
        actual_clean = actual.strip().lower()

        # 完全匹配
        if expected_clean == actual_clean:
            return True, 1.0

        # 包含关系
        if expected_clean in actual_clean:
            return True, 0.9

        if actual_clean in expected_clean:
            return True, 0.8

        # 数值匹配（对于数值答案）
        if self._is_numeric(expected_clean) and self._is_numeric(actual_clean):
            try:
                exp_num = float(expected_clean)
                act_num = float(actual_clean)
                if abs(exp_num - act_num) < 0.01:
                    return True, 1.0
                # 允许一定误差
                if abs(exp_num - act_num) / max(abs(exp_num), 1) < 0.05:
                    return True, 0.8
            except ValueError:
                pass

        # 部分匹配（计算相似度）
        similarity = self._calculate_similarity(expected_clean, actual_clean)
        if similarity > 0.8:
            return True, similarity
        elif similarity > 0.5:
            return False, similarity
        else:
            return False, 0.0

    def _is_numeric(self, s: str) -> bool:
        """检查字符串是否为数值"""
        try:
            float(s)
            return True
        except ValueError:
            return False

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """计算字符串相似度（简单实现）"""
        if not str1 or not str2:
            return 0.0

        # 使用集合交集
        words1 = set(str1.split())
        words2 = set(str2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _count_tool_calls(self, response: Any) -> int:
        """统计工具调用次数"""
        count = 0

        # 从响应中提取工具调用
        if hasattr(response, "tool_calls") and response.tool_calls:
            count += len(response.tool_calls)

        # 从消息历史中统计
        if hasattr(response, "messages"):
            for msg in response.messages:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    count += len(msg.tool_calls)

        return count

    def _generate_report(self) -> GAIAReport:
        """生成评估报告"""
        total = len(self.results)
        if total == 0:
            return GAIAReport(
                total_questions=0,
                correct_count=0,
                accuracy=0.0,
                average_score=0.0,
                average_time_ms=0.0,
                average_steps=0.0,
                average_tokens=0.0,
                average_tool_calls=0.0,
                results_by_difficulty={},
                results=[],
            )

        correct_count = sum(1 for r in self.results if r.correct)

        # 按难度分组统计
        results_by_difficulty: dict[str, list[GAIAResult]] = {}
        for result in self.results:
            difficulty = result.metadata.get("difficulty", "unknown")
            if difficulty not in results_by_difficulty:
                results_by_difficulty[difficulty] = []
            results_by_difficulty[difficulty].append(result)

        # 计算各难度指标
        difficulty_stats: dict[str, dict[str, float]] = {}
        for difficulty, results in results_by_difficulty.items():
            if results:
                difficulty_stats[difficulty] = {
                    "total": len(results),
                    "correct": sum(1 for r in results if r.correct),
                    "accuracy": sum(1 for r in results if r.correct) / len(results),
                    "avg_score": sum(r.score for r in results) / len(results),
                    "avg_time_ms": sum(r.time_taken_ms for r in results) / len(results),
                }

        return GAIAReport(
            total_questions=total,
            correct_count=correct_count,
            accuracy=correct_count / total,
            average_score=sum(r.score for r in self.results) / total,
            average_time_ms=sum(r.time_taken_ms for r in self.results) / total,
            average_steps=sum(r.steps_taken for r in self.results) / total,
            average_tokens=sum(r.tokens_used for r in self.results) / total,
            average_tool_calls=sum(r.tool_calls_count for r in self.results) / total,
            results_by_difficulty=difficulty_stats,
            results=self.results,
        )
