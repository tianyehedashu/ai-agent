"""
LLM-as-Judge 评估

使用 LLM 评估 Agent 响应质量
"""

import json
from typing import Any, ClassVar

from pydantic import BaseModel

from shared.infrastructure.llm.gateway import LLMGateway


class JudgeScore(BaseModel):
    """评分结果"""

    overall_score: float  # 0-10
    relevance: float  # 相关性
    accuracy: float  # 准确性
    completeness: float  # 完整性
    clarity: float  # 清晰度
    reasoning: str  # 评分理由


class LLMJudge:
    """LLM-as-Judge 评估器"""

    JUDGE_PROMPT = """You are an expert evaluator for AI assistant responses.

## Task
Evaluate the following response based on the given criteria.

## Input
**User Query:** {query}

**Expected Output (if any):** {expected}

**Actual Response:** {response}

## Evaluation Criteria
1. **Relevance (0-10):** Does the response address the user's query?
2. **Accuracy (0-10):** Is the information correct and factual?
3. **Completeness (0-10):** Does it fully answer the question?
4. **Clarity (0-10):** Is the response clear and well-structured?

## Output Format
Return a JSON object:
```json
{{
  "overall_score": 8.5,
  "relevance": 9,
  "accuracy": 8,
  "completeness": 8,
  "clarity": 9,
  "reasoning": "The response correctly addresses..."
}}
```

Evaluate now:"""

    def __init__(self, llm_gateway: LLMGateway, judge_model: str = "gpt-4"):
        self.llm = llm_gateway
        self.judge_model = judge_model

    async def evaluate(
        self,
        query: str,
        response: str,
        expected: str | None = None,
        criteria: dict[str, Any] | None = None,
    ) -> JudgeScore:
        """使用 LLM 评估响应质量"""
        prompt = self.JUDGE_PROMPT.format(
            query=query,
            expected=expected or "Not specified",
            response=response,
        )

        result = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.judge_model,
        )

        # 解析 JSON 响应
        content = result.content or "{}"
        # 提取 JSON 部分
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(content)
            return JudgeScore(**data)
        except Exception:
            # 如果解析失败，返回默认值
            return JudgeScore(
                overall_score=5.0,
                relevance=5.0,
                accuracy=5.0,
                completeness=5.0,
                clarity=5.0,
                reasoning="Failed to parse judge response",
            )

    async def compare(
        self,
        query: str,
        response_a: str,
        response_b: str,
    ) -> dict[str, Any]:
        """对比两个响应"""
        compare_prompt = """Compare these two responses to the same query.

Query: {query}

Response A:
{response_a}

Response B:
{response_b}

Which response is better? Return JSON:
{{
  "winner": "A" or "B" or "tie",
  "score_a": 0-10,
  "score_b": 0-10,
  "reasoning": "..."
}}"""

        result = await self.llm.chat(
            messages=[
                {
                    "role": "user",
                    "content": compare_prompt.format(
                        query=query,
                        response_a=response_a,
                        response_b=response_b,
                    ),
                },
            ],
            model=self.judge_model,
        )

        content = result.content or "{}"
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(content)
        except Exception:
            return {
                "winner": "tie",
                "score_a": 5.0,
                "score_b": 5.0,
                "reasoning": "Failed to parse comparison",
            }


class MultiDimensionJudge:
    """多维度评估器"""

    DIMENSIONS: ClassVar[dict[str, str]] = {
        "helpfulness": "How helpful is the response in addressing the user's needs?",
        "harmlessness": "Is the response free from harmful or dangerous content?",
        "honesty": "Is the response honest and not misleading?",
        "factuality": "Are the facts in the response accurate?",
        "coherence": "Is the response logically coherent and well-structured?",
    }

    def __init__(self, llm_gateway: LLMGateway, judge_model: str = "gpt-4"):
        self.llm = llm_gateway
        self.judge_model = judge_model

    async def evaluate_all_dimensions(
        self,
        query: str,
        response: str,
    ) -> dict[str, float]:
        """评估所有维度"""
        scores: dict[str, float] = {}

        for dim, description in self.DIMENSIONS.items():
            score = await self._evaluate_dimension(
                query=query,
                response=response,
                dimension=dim,
                description=description,
            )
            scores[dim] = score

        scores["overall"] = sum(scores.values()) / len(scores)
        return scores

    async def _evaluate_dimension(
        self,
        query: str,
        response: str,
        dimension: str,
        description: str,
    ) -> float:
        """评估单个维度"""
        prompt = f"""Evaluate the following response on the dimension: {dimension}

Description: {description}

Query: {query}
Response: {response}

Rate from 0-10. Return only the number."""

        result = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.judge_model,
        )

        try:
            score = float(result.content or "5.0")
            return max(0.0, min(10.0, score))
        except Exception:
            return 5.0
