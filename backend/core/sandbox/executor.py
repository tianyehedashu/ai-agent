"""
Sandbox Executor - 沙箱执行器

实现安全的代码执行:
- Docker 隔离
- 资源限制
- 超时控制
"""

import asyncio
import tempfile
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel

from app.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class ExecutionResult(BaseModel):
    """执行结果"""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    error: str | None = None


class SandboxConfig(BaseModel):
    """沙箱配置"""

    timeout_seconds: int = 30
    memory_limit_mb: int = 256
    cpu_limit: float = 1.0
    network_enabled: bool = False
    read_only_root: bool = True


class SandboxExecutor(ABC):
    """沙箱执行器抽象基类"""

    @abstractmethod
    async def execute_python(
        self,
        code: str,
        config: SandboxConfig | None = None,
    ) -> ExecutionResult:
        """执行 Python 代码"""
        ...

    @abstractmethod
    async def execute_shell(
        self,
        command: str,
        config: SandboxConfig | None = None,
    ) -> ExecutionResult:
        """执行 Shell 命令"""
        ...


class DockerExecutor(SandboxExecutor):
    """
    Docker 沙箱执行器

    使用 Docker 容器提供隔离的执行环境
    """

    def __init__(
        self,
        python_image: str = "python:3.11-slim",
        shell_image: str = "alpine:latest",
    ) -> None:
        self.python_image = python_image
        self.shell_image = shell_image

    async def execute_python(
        self,
        code: str,
        config: SandboxConfig | None = None,
    ) -> ExecutionResult:
        """
        在 Docker 容器中执行 Python 代码

        Args:
            code: Python 代码
            config: 沙箱配置

        Returns:
            ExecutionResult: 执行结果
        """
        config = config or SandboxConfig()

        # 创建临时文件存放代码 (使用 asyncio.to_thread 包装同步操作)
        def create_temp_file() -> str:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
            ) as f:
                f.write(code)
                return f.name

        code_file = await asyncio.to_thread(create_temp_file)

        try:
            # 构建 Docker 命令
            cmd = self._build_docker_command(
                image=self.python_image,
                command="python /code/script.py",
                volumes={code_file: "/code/script.py"},
                config=config,
            )

            return await self._run_container(cmd, config.timeout_seconds)

        finally:
            # 清理临时文件
            Path(code_file).unlink(missing_ok=True)

    async def execute_shell(
        self,
        command: str,
        config: SandboxConfig | None = None,
    ) -> ExecutionResult:
        """
        在 Docker 容器中执行 Shell 命令

        Args:
            command: Shell 命令
            config: 沙箱配置

        Returns:
            ExecutionResult: 执行结果
        """
        config = config or SandboxConfig()

        # 构建 Docker 命令
        cmd = self._build_docker_command(
            image=self.shell_image,
            command=f"sh -c '{command}'",
            volumes={},
            config=config,
        )

        return await self._run_container(cmd, config.timeout_seconds)

    def _build_docker_command(
        self,
        image: str,
        command: str,
        volumes: dict[str, str],
        config: SandboxConfig,
    ) -> list[str]:
        """构建 Docker 运行命令"""
        cmd = [
            "docker",
            "run",
            "--rm",
            "--name",
            f"sandbox-{uuid.uuid4().hex[:8]}",
        ]

        # 资源限制
        cmd.extend(["--memory", f"{config.memory_limit_mb}m"])
        cmd.extend(["--cpus", str(config.cpu_limit)])

        # 网络隔离
        if not config.network_enabled:
            cmd.extend(["--network", "none"])

        # 只读根文件系统
        if config.read_only_root:
            cmd.append("--read-only")
            # 添加临时目录
            cmd.extend(["--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])

        # 挂载卷
        for host_path, container_path in volumes.items():
            cmd.extend(["-v", f"{host_path}:{container_path}:ro"])

        # 镜像和命令
        cmd.append(image)
        cmd.extend(["sh", "-c", command])

        return cmd

    async def _run_container(
        self,
        cmd: list[str],
        timeout: int,  # noqa: ASYNC109 - 使用 asyncio.wait_for 实现超时
    ) -> ExecutionResult:
        """运行 Docker 容器"""
        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="",
                    exit_code=-1,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=f"Execution timed out after {timeout} seconds",
                )

            duration_ms = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error(f"Docker execution error: {e}")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                duration_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )


class LocalExecutor(SandboxExecutor):
    """
    本地执行器 (仅开发环境)

    警告: 不安全，仅用于开发测试
    """

    async def execute_python(
        self,
        code: str,
        config: SandboxConfig | None = None,
    ) -> ExecutionResult:
        """执行 Python 代码 (本地)"""
        config = config or SandboxConfig()
        start_time = time.time()

        # 创建临时文件 (使用 asyncio.to_thread 包装同步操作)
        def create_temp_file() -> str:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
            ) as f:
                f.write(code)
                return f.name

        code_file = await asyncio.to_thread(create_temp_file)

        try:
            process = await asyncio.create_subprocess_exec(
                "python",
                code_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=config.timeout_seconds,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="",
                    exit_code=-1,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error="Execution timed out",
                )

            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0,
                duration_ms=int((time.time() - start_time) * 1000),
            )

        finally:
            Path(code_file).unlink(missing_ok=True)

    async def execute_shell(
        self,
        command: str,
        config: SandboxConfig | None = None,
    ) -> ExecutionResult:
        """执行 Shell 命令 (本地)"""
        config = config or SandboxConfig()
        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=settings.work_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=config.timeout_seconds,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="",
                    exit_code=-1,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error="Execution timed out",
                )

            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0,
                duration_ms=int((time.time() - start_time) * 1000),
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                duration_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
