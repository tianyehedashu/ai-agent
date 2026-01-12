"""
Code Tools - 代码操作工具
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pydantic import Field

from app.config import settings
from core.types import ToolCategory, ToolResult
from tools.base import BaseTool, ToolParameters, register_tool


class RunShellParams(ToolParameters):
    """运行 Shell 命令参数"""

    command: str = Field(description="要执行的 Shell 命令")
    cwd: str | None = Field(default=None, description="工作目录")
    timeout: int = Field(default=60, description="超时时间 (秒)")


class RunPythonParams(ToolParameters):
    """运行 Python 代码参数"""

    code: str = Field(description="Python 代码")
    timeout: int = Field(default=30, description="超时时间 (秒)")


class SearchCodeParams(ToolParameters):
    """代码搜索参数"""

    pattern: str = Field(description="搜索模式 (正则表达式)")
    path: str = Field(default=".", description="搜索路径")
    file_pattern: str = Field(default="*", description="文件名模式")


@register_tool
class RunShellTool(BaseTool):
    """运行 Shell 命令工具"""

    name = "run_shell"
    description = "在系统 Shell 中执行命令"
    category = ToolCategory.CODE
    requires_confirmation = True
    parameters_model = RunShellParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        params = RunShellParams(**kwargs)

        try:
            cwd = params.cwd or settings.work_dir

            result = subprocess.run(
                params.command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=params.timeout,
            )

            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"

            return ToolResult(
                tool_call_id="",
                success=result.returncode == 0,
                output=output.strip(),
                error=f"Exit code: {result.returncode}" if result.returncode != 0 else None,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"Command timed out after {params.timeout} seconds",
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=str(e),
            )


@register_tool
class RunPythonTool(BaseTool):
    """运行 Python 代码工具"""

    name = "run_python"
    description = "在隔离环境中执行 Python 代码"
    category = ToolCategory.CODE
    requires_confirmation = True
    parameters_model = RunPythonParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        params = RunPythonParams(**kwargs)

        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
            ) as f:
                f.write(params.code)
                temp_path = f.name

            try:
                result = subprocess.run(
                    ["python", temp_path],
                    capture_output=True,
                    text=True,
                    timeout=params.timeout,
                    cwd=settings.work_dir,
                )

                output = result.stdout
                if result.stderr:
                    output += f"\nSTDERR:\n{result.stderr}"

                return ToolResult(
                    tool_call_id="",
                    success=result.returncode == 0,
                    output=output.strip(),
                    error=f"Exit code: {result.returncode}" if result.returncode != 0 else None,
                )
            finally:
                Path(temp_path).unlink()

        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"Execution timed out after {params.timeout} seconds",
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=str(e),
            )


@register_tool
class SearchCodeTool(BaseTool):
    """代码搜索工具"""

    name = "search_code"
    description = "使用正则表达式在代码库中搜索"
    category = ToolCategory.CODE
    requires_confirmation = False
    parameters_model = SearchCodeParams

    async def execute(self, **kwargs: Any) -> ToolResult:
        params = SearchCodeParams(**kwargs)

        try:
            search_path = Path(settings.work_dir) / params.path

            if not search_path.exists():
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output="",
                    error=f"Path not found: {params.path}",
                )

            # 使用 grep 进行搜索
            cmd = [
                "grep",
                "-r",
                "-n",
                "-E",
                params.pattern,
                "--include",
                params.file_pattern,
                str(search_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 1 and not result.stdout:
                return ToolResult(
                    tool_call_id="",
                    success=True,
                    output="No matches found",
                )

            return ToolResult(
                tool_call_id="",
                success=True,
                output=result.stdout.strip(),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error="Search timed out",
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=str(e),
            )
