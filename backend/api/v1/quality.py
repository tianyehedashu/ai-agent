"""
Quality API - 代码质量 API

实现:
- POST /quality/validate: 代码验证
- POST /quality/fix: 代码修复
- POST /quality/format: 代码格式化
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shared.presentation import get_current_user
from bootstrap.config import settings
from shared.infrastructure.llm.gateway import LLMGateway
from domains.studio.infrastructure.lsp.proxy import LSPProxy
from domains.studio.infrastructure.quality.fixer import CodeFixer
from domains.studio.infrastructure.quality.validator import CodeValidator

# 默认文件路径常量
DEFAULT_FILE_PATH = "code.py"

router = APIRouter(prefix="/quality", tags=["Quality"])


class ValidateRequest(BaseModel):
    """验证请求"""

    code: str
    file_path: str = DEFAULT_FILE_PATH
    check_syntax: bool = True
    check_types: bool = True
    check_lint: bool = True
    check_architecture: bool = True


class FixRequest(BaseModel):
    """修复请求"""

    code: str
    max_attempts: int = 3


class FormatRequest(BaseModel):
    """格式化请求"""

    code: str
    file_path: str = DEFAULT_FILE_PATH


class DiagnosticsRequest(BaseModel):
    """诊断请求"""

    code: str
    file_path: str = DEFAULT_FILE_PATH


@router.post("/validate")
async def validate_code(
    request: ValidateRequest,
    _current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    验证代码

    返回语法、类型、Lint、架构规范的检查结果
    """
    validator = CodeValidator()
    result = await validator.validate(
        code=request.code,
        file_path=request.file_path,
        check_syntax=request.check_syntax,
        check_types=request.check_types,
        check_lint=request.check_lint,
        check_architecture=request.check_architecture,
    )

    return {
        "is_valid": result.is_valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "issues": [
            {
                "line": i.line,
                "column": i.column,
                "severity": i.severity.value,
                "message": i.message,
                "code": i.code,
                "source": i.source,
            }
            for i in result.issues
        ],
    }


@router.post("/fix")
async def fix_code(
    request: FixRequest,
    _current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    修复代码

    使用 LLM 自动修复代码问题
    """
    llm_gateway = LLMGateway(config=settings)
    fixer = CodeFixer(llm=llm_gateway, max_attempts=request.max_attempts)
    fixed_code, success = await fixer.fix(request.code)

    return {
        "success": success,
        "original_code": request.code,
        "fixed_code": fixed_code,
    }


@router.post("/format")
async def format_code(
    request: FormatRequest,
    _current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """
    格式化代码

    使用 Ruff 格式化 Python 代码
    """
    lsp = LSPProxy()
    formatted = await lsp.format_code(request.file_path, request.code)

    return {
        "original_code": request.code,
        "formatted_code": formatted,
    }


@router.post("/diagnostics")
async def get_diagnostics(
    request: DiagnosticsRequest,
    _current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """
    获取诊断信息

    返回 Pyright 和 Ruff 的诊断结果
    """
    lsp = LSPProxy()
    diagnostics = await lsp.get_diagnostics(request.file_path, request.code)

    return diagnostics


class CompletionRequest(BaseModel):
    """代码补全请求"""

    code: str
    language: str = "python"
    line: int
    column: int
    file_path: str = DEFAULT_FILE_PATH


class HoverRequest(BaseModel):
    """悬停信息请求"""

    code: str
    language: str = "python"
    line: int
    column: int
    file_path: str = DEFAULT_FILE_PATH


@router.post("/completion")
async def get_completion(
    request: CompletionRequest,
    _current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    获取代码补全建议

    返回基于当前位置的补全列表
    """
    lsp = LSPProxy()
    completions = await lsp.get_completions(
        file_path=request.file_path,
        content=request.code,
        line=request.line,
        column=request.column,
    )

    return {
        "data": completions,
    }


@router.post("/hover")
async def get_hover(
    request: HoverRequest,
    _current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    获取悬停信息

    返回光标位置的类型信息和文档
    """
    lsp = LSPProxy()
    hover_info = await lsp.get_hover(
        file_path=request.file_path,
        content=request.code,
        line=request.line,
        column=request.column,
    )

    return {
        "data": hover_info,
    }
