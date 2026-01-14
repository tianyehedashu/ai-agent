"""
评估 API 端点

提供评估功能的 API 接口
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.deps import get_current_user
from core.llm.gateway import LLMGateway
from core.types import ToolCall
from evaluation.gaia import GAIAEvaluator, GAIAReport
from evaluation.llm_judge import JudgeScore, LLMJudge
from evaluation.task_completion import EvaluationReport
from evaluation.tool_accuracy import ToolAccuracyEvaluator, ToolAccuracyReport
from models.user import User

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


class EvaluationRequest(BaseModel):
    """评估请求"""

    agent_id: str
    benchmark_type: str  # "task", "gaia", "tool_accuracy"
    benchmark_path: str | None = None
    test_cases: list[dict[str, Any]] | None = None


class ToolAccuracyRequest(BaseModel):
    """工具准确率评估请求"""

    tool_calls: list[dict[str, Any]]
    expected_tools: dict[str, str] | None = None  # tool_call_id -> expected_tool
    expected_args: dict[str, dict[str, Any]] | None = None  # tool_call_id -> expected_args


class LLMJudgeRequest(BaseModel):
    """LLM-as-Judge 评估请求"""

    query: str
    response: str
    expected: str | None = None
    judge_model: str = "gpt-4"


@router.post("/task", response_model=EvaluationReport)
async def evaluate_task_completion(
    request: EvaluationRequest,
    current_user: User = Depends(get_current_user),
):
    """任务完成率评估"""
    if request.benchmark_type != "task":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid benchmark type for task evaluation",
        )

    if not request.test_cases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="test_cases is required",
        )

    # TODO: 实现完整评估流程:
    # 1. 从数据库加载 Agent
    # 2. 创建评估器并运行评估
    _ = (request, current_user)  # 抑制未使用警告，待实现

    # 临时返回示例
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Task evaluation not fully implemented yet",
    )


@router.post("/gaia", response_model=GAIAReport)
async def evaluate_gaia(
    request: EvaluationRequest,
    current_user: User = Depends(get_current_user),
):
    """GAIA 基准评估"""
    if request.benchmark_type != "gaia":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid benchmark type for GAIA evaluation",
        )

    # 创建评估器
    evaluator = GAIAEvaluator()

    # 加载基准测试集
    if request.benchmark_path:
        benchmark_path = Path(request.benchmark_path)
        if not benchmark_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Benchmark file not found: {request.benchmark_path}",
            )
        evaluator.load_benchmark(benchmark_path)
    else:
        # 使用默认的 GAIA 基准
        default_path = (
            Path(__file__).parent.parent.parent / "evaluation" / "benchmarks" / "gaia_sample.yaml"
        )
        if default_path.exists():
            evaluator.load_benchmark(default_path)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No benchmark file provided and default not found",
            )

    # TODO: 实现完整评估流程:
    # 1. 从数据库加载 Agent
    # 2. 使用真实 Agent 实例运行 GAIA 评估
    _ = current_user  # 抑制未使用警告，待实现

    # 临时返回示例
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="GAIA evaluation not fully implemented yet",
    )


@router.post("/tool-accuracy", response_model=ToolAccuracyReport)
async def evaluate_tool_accuracy(
    request: ToolAccuracyRequest,
    current_user: User = Depends(get_current_user),
):
    """工具调用准确率评估"""
    evaluator = ToolAccuracyEvaluator()

    for tool_call_data in request.tool_calls:
        tool_call = ToolCall(**tool_call_data)

        expected_tool = None
        expected_args = None
        if request.expected_tools and tool_call.id in request.expected_tools:
            expected_tool = request.expected_tools[tool_call.id]
        if request.expected_args and tool_call.id in request.expected_args:
            expected_args = request.expected_args[tool_call.id]

        evaluator.evaluate_tool_call(
            tool_call=tool_call,
            expected_tool=expected_tool,
            expected_args=expected_args,
        )

    return evaluator.generate_report()


@router.post("/llm-judge", response_model=JudgeScore)
async def evaluate_with_llm_judge(
    request: LLMJudgeRequest,
    current_user: User = Depends(get_current_user),
):
    """使用 LLM-as-Judge 评估响应质量"""
    llm_gateway = LLMGateway()
    judge = LLMJudge(llm_gateway=llm_gateway, judge_model=request.judge_model)

    score = await judge.evaluate(
        query=request.query,
        response=request.response,
        expected=request.expected,
    )

    return score


@router.get("/benchmarks")
async def list_benchmarks(
    current_user: User = Depends(get_current_user),
):
    """列出可用的基准测试集"""
    benchmarks_dir = Path(__file__).parent.parent.parent / "evaluation" / "benchmarks"

    benchmarks = []
    if benchmarks_dir.exists():
        for file_path in benchmarks_dir.glob("*.yaml"):
            benchmarks.append(
                {
                    "name": file_path.stem,
                    "path": str(file_path.relative_to(benchmarks_dir.parent.parent)),
                    "type": "yaml",
                }
            )
        for file_path in benchmarks_dir.glob("*.json"):
            benchmarks.append(
                {
                    "name": file_path.stem,
                    "path": str(file_path.relative_to(benchmarks_dir.parent.parent)),
                    "type": "json",
                }
            )

    return {"benchmarks": benchmarks}
