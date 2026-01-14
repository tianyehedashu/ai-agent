"""
Code Tools - 代码操作工具
"""

import asyncio
from pathlib import Path
import tempfile
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

            process = await asyncio.create_subprocess_shell(
                params.command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=params.timeout,
                )
            except TimeoutError:
                process.kill()
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output="",
                    error=f"Command timed out after {params.timeout} seconds",
                )

            output = stdout.decode()
            if stderr:
                output += f"\nSTDERR:\n{stderr.decode()}"

            return ToolResult(
                tool_call_id="",
                success=process.returncode == 0,
                output=output.strip(),
                error=f"Exit code: {process.returncode}" if process.returncode != 0 else None,
            )
        except (OSError, ValueError, TypeError) as e:
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
            # 创建临时文件 (使用 asyncio.to_thread 包装同步操作)
            def create_temp_file() -> str:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".py",
                    delete=False,
                ) as f:
                    f.write(params.code)
                    return f.name

            temp_path = await asyncio.to_thread(create_temp_file)

            try:
                process = await asyncio.create_subprocess_exec(
                    "python",
                    temp_path,
                    cwd=settings.work_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=params.timeout,
                    )
                except TimeoutError:
                    process.kill()
                    return ToolResult(
                        tool_call_id="",
                        success=False,
                        output="",
                        error=f"Execution timed out after {params.timeout} seconds",
                    )

                output = stdout.decode()
                if stderr:
                    output += f"\nSTDERR:\n{stderr.decode()}"

                return ToolResult(
                    tool_call_id="",
                    success=process.returncode == 0,
                    output=output.strip(),
                    error=f"Exit code: {process.returncode}" if process.returncode != 0 else None,
                )
            finally:
                await asyncio.to_thread(Path(temp_path).unlink)

        except (OSError, ValueError, TypeError, FileNotFoundError) as e:
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

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, _ = await asyncio.wait_for(
                    process.communicate(),
                    timeout=30,
                )
            except TimeoutError:
                process.kill()
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output="",
                    error="Search timed out",
                )

            if process.returncode == 1 and not stdout:
                return ToolResult(
                    tool_call_id="",
                    success=True,
                    output="No matches found",
                )

            return ToolResult(
                tool_call_id="",
                success=True,
                output=stdout.decode().strip(),
            )
        except TimeoutError:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error="Search timed out",
            )
        except (OSError, ValueError, TypeError, FileNotFoundError) as e:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=str(e),
            )
