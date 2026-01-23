"""
工具调用准确率评估

评估 Agent 工具调用的准确性和正确性
"""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from shared.types import ToolCall, ToolResult


@dataclass
class ToolCallEvalResult:
    """工具调用评估结果"""

    tool_call_id: str
    tool_name: str
    expected_tool: str | None  # 期望的工具名称
    expected_args: dict[str, Any] | None  # 期望的参数
    actual_args: dict[str, Any]  # 实际参数
    correct_tool: bool  # 工具选择是否正确
    correct_args: bool  # 参数是否正确
    args_accuracy: float  # 参数准确度 (0.0 - 1.0)
    execution_success: bool  # 执行是否成功
    overall_score: float  # 总体得分 (0.0 - 1.0)


class ToolAccuracyReport(BaseModel):
    """工具准确率报告"""

    total_calls: int
    correct_tool_count: int
    correct_args_count: int
    execution_success_count: int
    tool_accuracy: float  # 工具选择准确率
    args_accuracy: float  # 参数准确率
    execution_success_rate: float  # 执行成功率
    overall_accuracy: float  # 总体准确率
    results: list[ToolCallEvalResult]


class ToolAccuracyEvaluator:
    """工具调用准确率评估器"""

    def __init__(self):
        self.results: list[ToolCallEvalResult] = []

    def evaluate_tool_call(
        self,
        tool_call: ToolCall,
        tool_result: ToolResult | None = None,
        expected_tool: str | None = None,
        expected_args: dict[str, Any] | None = None,
    ) -> ToolCallEvalResult:
        """评估单个工具调用"""

        # 评估工具选择
        correct_tool = True
        if expected_tool:
            correct_tool = tool_call.name == expected_tool

        # 评估参数
        correct_args = True
        args_accuracy = 1.0
        if expected_args:
            correct_args, args_accuracy = self._evaluate_args(
                expected=expected_args,
                actual=tool_call.arguments,
            )

        # 评估执行结果
        execution_success = tool_result.success if tool_result else False

        # 计算总体得分
        overall_score = self._calculate_overall_score(
            correct_tool=correct_tool,
            correct_args=correct_args,
            args_accuracy=args_accuracy,
            execution_success=execution_success,
        )

        result = ToolCallEvalResult(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            expected_tool=expected_tool,
            expected_args=expected_args,
            actual_args=tool_call.arguments,
            correct_tool=correct_tool,
            correct_args=correct_args,
            args_accuracy=args_accuracy,
            execution_success=execution_success,
            overall_score=overall_score,
        )

        self.results.append(result)
        return result

    def _evaluate_args(
        self,
        expected: dict[str, Any],
        actual: dict[str, Any],
    ) -> tuple[bool, float]:
        """评估参数准确性"""
        if not expected:
            return True, 1.0

        if not actual:
            return False, 0.0

        # 检查必需参数
        correct = True
        accuracy_scores = []

        for key, expected_value in expected.items():
            if key not in actual:
                correct = False
                accuracy_scores.append(0.0)
                continue

            actual_value = actual[key]
            score = self._compare_values(expected_value, actual_value)
            accuracy_scores.append(score)

            if score < 1.0:
                correct = False

        # 计算平均准确度
        avg_accuracy = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0.0

        return correct, avg_accuracy

    def _compare_values(self, expected: Any, actual: Any) -> float:
        """比较两个值，返回相似度 (0.0 - 1.0)"""
        # 完全匹配
        if expected == actual:
            return 1.0

        # 类型匹配但值不同
        if type(expected) is type(actual):
            # 字符串相似度
            if isinstance(expected, str):
                return self._string_similarity(expected, actual)
            # 数值接近度
            if isinstance(expected, int | float):
                return self._numeric_similarity(expected, actual)
            # 列表/字典相似度
            if isinstance(expected, list | dict):
                return 0.5  # 部分匹配

        return 0.0

    def _string_similarity(self, str1: str, str2: str) -> float:
        """计算字符串相似度"""
        str1_lower = str1.lower().strip()
        str2_lower = str2.lower().strip()

        # 完全匹配
        if str1_lower == str2_lower:
            return 1.0

        # 包含关系
        if str1_lower in str2_lower or str2_lower in str1_lower:
            return 0.8

        # 计算字符重叠度
        set1 = set(str1_lower)
        set2 = set(str2_lower)
        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _numeric_similarity(self, num1: float, num2: float) -> float:
        """计算数值相似度"""
        if num1 == 0 and num2 == 0:
            return 1.0

        if num1 == 0 or num2 == 0:
            return 0.0

        ratio = min(num1, num2) / max(num1, num2)
        return ratio

    def _calculate_overall_score(
        self,
        correct_tool: bool,
        correct_args: bool,
        args_accuracy: float,
        execution_success: bool,
    ) -> float:
        """计算总体得分"""
        # 权重分配
        tool_weight = 0.3  # 工具选择权重
        args_weight = 0.4  # 参数权重
        execution_weight = 0.3  # 执行权重

        score = 0.0

        # 工具选择得分
        score += tool_weight * (1.0 if correct_tool else 0.0)

        # 参数得分
        score += args_weight * args_accuracy

        # 执行得分
        # 如果执行失败，即使工具和参数都正确，也应该显著降低分数
        if execution_success:
            score += execution_weight * 1.0
        else:
            # 执行失败时，执行得分降为0，并且对总分进行惩罚
            score *= 0.8  # 执行失败时总分打8折

        return score

    def generate_report(self) -> ToolAccuracyReport:
        """生成评估报告"""
        total = len(self.results)
        if total == 0:
            return ToolAccuracyReport(
                total_calls=0,
                correct_tool_count=0,
                correct_args_count=0,
                execution_success_count=0,
                tool_accuracy=0.0,
                args_accuracy=0.0,
                execution_success_rate=0.0,
                overall_accuracy=0.0,
                results=[],
            )

        correct_tool_count = sum(1 for r in self.results if r.correct_tool)
        correct_args_count = sum(1 for r in self.results if r.correct_args)
        execution_success_count = sum(1 for r in self.results if r.execution_success)

        avg_args_accuracy = sum(r.args_accuracy for r in self.results) / total
        avg_overall_score = sum(r.overall_score for r in self.results) / total

        return ToolAccuracyReport(
            total_calls=total,
            correct_tool_count=correct_tool_count,
            correct_args_count=correct_args_count,
            execution_success_count=execution_success_count,
            tool_accuracy=correct_tool_count / total,
            args_accuracy=avg_args_accuracy,
            execution_success_rate=execution_success_count / total,
            overall_accuracy=avg_overall_score,
            results=self.results,
        )

    def reset(self):
        """重置评估器"""
        self.results = []
