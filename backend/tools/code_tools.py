"""
Code Tools - 代码操作工具

使用沙箱执行器实现安全的代码执行：
- Docker 模式（生产环境推荐）：在容器中隔离执行
- Local 模式（开发环境）：本地直接执行
"""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import Field

from app.config import settings
from core.sandbox.executor import SandboxConfig as SandboxExecConfig
from core.sandbox.factory import ExecutorFactory
from core.types import ToolCategory, ToolResult
from tools.base import BaseTool, ToolParameters, register_tool
from utils.logging import get_logger

if TYPE_CHECKING:
    from core.config.execution_config import ExecutionConfig

logger = get_logger(__name__)


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


def _parse_memory_limit(limit: str) -> int:
    """解析内存限制字符串为 MB 数值"""
    limit = limit.lower().strip()
    if limit.endswith("g"):
        return int(float(limit[:-1]) * 1024)
    if limit.endswith("m"):
        return int(float(limit[:-1]))
    if limit.endswith("k"):
        return max(1, int(float(limit[:-1]) / 1024))
    return int(limit)


@register_tool
class RunShellTool(BaseTool):
    """
    运行 Shell 命令工具

    根据配置在沙箱（Docker）或本地环境中执行 Shell 命令。
    生产环境应使用 Docker 模式以确保安全隔离。
    """

    name = "run_shell"
    description = "在沙箱环境中执行 Shell 命令（支持 Docker 隔离或本地执行）"
    category = ToolCategory.CODE
    requires_confirmation = True
    parameters_model = RunShellParams

    # 运行时配置（由 ToolRegistry 注入）
    execution_config: ClassVar["ExecutionConfig | None"] = None

    async def execute(self, **kwargs: Any) -> ToolResult:
        params = RunShellParams(**kwargs)

        try:
            # 获取沙箱执行器
            executor = ExecutorFactory.create(self.execution_config)

            # 构建沙箱配置
            sandbox_config = self._build_sandbox_config(params.timeout)

            logger.debug(
                "Executing shell command in %s mode: %s",
                self.execution_config.sandbox.mode if self.execution_config else "local",
                params.command[:100],
            )

            # 在沙箱中执行
            result = await executor.execute_shell(
                command=params.command,
                config=sandbox_config,
            )

            # 转换为 ToolResult
            if result.success:
                output = result.stdout
                if result.stderr:
                    output += f"\nSTDERR:\n{result.stderr}"
                return ToolResult(
                    tool_call_id="",
                    success=True,
                    output=output.strip(),
                    error=None,
                    duration_ms=result.duration_ms,
                )
            else:
                error_parts = [f"Exit code: {result.exit_code}"]
                if result.error:
                    error_parts.append(result.error)
                elif result.stderr:
                    error_parts.append(f"Error output: {result.stderr}")
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output=result.stdout,
                    error="; ".join(error_parts),
                    duration_ms=result.duration_ms,
                )

        except NotImplementedError as e:
            # 沙箱模式不可用（如 remote 模式未实现）
            logger.warning("Sandbox mode not available: %s", e)
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"Sandbox not available: {e}",
            )
        except Exception as e:
            logger.exception("Shell execution error: %s", e)
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"{type(e).__name__}: {e!s}",
            )

    def _build_sandbox_config(self, timeout: int) -> SandboxExecConfig:
        """构建沙箱执行配置"""
        if self.execution_config:
            sandbox = self.execution_config.sandbox
            return SandboxExecConfig(
                timeout_seconds=timeout,
                memory_limit_mb=_parse_memory_limit(sandbox.resources.memory_limit),
                cpu_limit=sandbox.resources.cpu_limit,
                network_enabled=sandbox.network.enabled,
                read_only_root=sandbox.security.read_only_root,
            )
        # 使用默认配置
        return SandboxExecConfig(timeout_seconds=timeout)


@register_tool
class RunPythonTool(BaseTool):
    """
    运行 Python 代码工具

    根据配置在沙箱（Docker）或本地环境中执行 Python 代码。
    生产环境应使用 Docker 模式以确保安全隔离。
    """

    name = "run_python"
    description = "在沙箱环境中执行 Python 代码（支持 Docker 隔离或本地执行）"
    category = ToolCategory.CODE
    requires_confirmation = True
    parameters_model = RunPythonParams

    # 运行时配置（由 ToolRegistry 注入）
    execution_config: ClassVar["ExecutionConfig | None"] = None

    async def execute(self, **kwargs: Any) -> ToolResult:
        params = RunPythonParams(**kwargs)

        try:
            # 获取沙箱执行器
            executor = ExecutorFactory.create(self.execution_config)

            # 构建沙箱配置
            sandbox_config = self._build_sandbox_config(params.timeout)

            logger.debug(
                "Executing Python code in %s mode",
                self.execution_config.sandbox.mode if self.execution_config else "local",
            )

            # 在沙箱中执行
            result = await executor.execute_python(
                code=params.code,
                config=sandbox_config,
            )

            # 转换为 ToolResult
            if result.success:
                output = result.stdout
                if result.stderr:
                    output += f"\nSTDERR:\n{result.stderr}"
                return ToolResult(
                    tool_call_id="",
                    success=True,
                    output=output.strip(),
                    error=None,
                    duration_ms=result.duration_ms,
                )
            else:
                error_parts = [f"Exit code: {result.exit_code}"]
                if result.error:
                    error_parts.append(result.error)
                elif result.stderr:
                    error_parts.append(f"Error output: {result.stderr}")
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output=result.stdout,
                    error="; ".join(error_parts),
                    duration_ms=result.duration_ms,
                )

        except NotImplementedError as e:
            logger.warning("Sandbox mode not available: %s", e)
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"Sandbox not available: {e}",
            )
        except Exception as e:
            logger.exception("Python execution error: %s", e)
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"{type(e).__name__}: {e!s}",
            )

    def _build_sandbox_config(self, timeout: int) -> SandboxExecConfig:
        """构建沙箱执行配置"""
        if self.execution_config:
            sandbox = self.execution_config.sandbox
            return SandboxExecConfig(
                timeout_seconds=timeout,
                memory_limit_mb=_parse_memory_limit(sandbox.resources.memory_limit),
                cpu_limit=sandbox.resources.cpu_limit,
                network_enabled=sandbox.network.enabled,
                read_only_root=sandbox.security.read_only_root,
            )
        return SandboxExecConfig(timeout_seconds=timeout)


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
