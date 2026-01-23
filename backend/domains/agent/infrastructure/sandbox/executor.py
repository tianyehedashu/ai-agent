"""
Sandbox Executor - 沙箱执行器

实现安全的代码执行:
- Docker 隔离
- 资源限制
- 超时控制
"""

from abc import ABC, abstractmethod
import asyncio
import contextlib
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

from pydantic import BaseModel

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

        # 构建 Docker 命令（命令会在 _build_docker_command 中用 sh -c 包装）
        cmd = self._build_docker_command(
            image=self.shell_image,
            command=command,  # 直接传递命令，不要预先包装
            volumes={},
            config=config,
        )

        logger.debug("Docker shell command: %s", " ".join(cmd))
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

        # 设置 UTF-8 环境变量，确保容器内输出正确的编码
        cmd.extend(["-e", "LANG=C.UTF-8"])
        cmd.extend(["-e", "LC_ALL=C.UTF-8"])

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
        timeout: int,
    ) -> ExecutionResult:
        """运行 Docker 容器

        使用 subprocess.run 在线程池中执行，以兼容 Windows 平台
        """
        start_time = time.time()

        def run() -> tuple[int, str, str, str | None]:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=timeout,
                    text=True,
                    encoding="utf-8",
                    errors="replace",  # 替换无法解码的字符，避免崩溃
                    check=False,
                )
                return (result.returncode, result.stdout, result.stderr, None)
            except subprocess.TimeoutExpired:
                return (-1, "", "", f"Execution timed out after {timeout} seconds")
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                return (-1, "", "", error_msg)

        returncode, stdout, stderr, error = await asyncio.to_thread(run)
        duration_ms = int((time.time() - start_time) * 1000)

        return ExecutionResult(
            success=returncode == 0 and error is None,
            stdout=stdout.strip(),
            stderr=stderr.strip(),
            exit_code=returncode,
            duration_ms=duration_ms,
            error=error,
        )


class SessionDockerExecutor(SandboxExecutor):
    """
    会话级 Docker 沙箱执行器

    特点：
    - 容器在会话期间保持运行
    - 支持持久化卷，文件跨命令保留
    - 安装的包在会话内保留
    - 支持容器自动过期清理
    """

    # 容器名称前缀，用于识别和清理
    CONTAINER_PREFIX = "session-"

    def __init__(
        self,
        image: str = "python:3.11-slim",
        workspace_path: str | None = None,
        container_workspace: str = "/workspace",
        max_idle_seconds: int = 3600,  # 最大空闲时间（默认 1 小时）
    ) -> None:
        """
        初始化会话执行器

        Args:
            image: Docker 镜像
            workspace_path: 主机工作目录路径（用于持久化）
            container_workspace: 容器内工作目录
            max_idle_seconds: 容器最大空闲时间（秒），超时自动清理
        """
        self.image = image
        self.workspace_path = workspace_path
        self.container_workspace = container_workspace
        self.max_idle_seconds = max_idle_seconds
        self._container_id: str | None = None
        self._session_id: str | None = None
        self._last_activity: float = 0

    @property
    def is_running(self) -> bool:
        """检查会话容器是否运行中"""
        return self._container_id is not None

    @property
    def session_id(self) -> str | None:
        """获取会话 ID"""
        return self._session_id

    @property
    def container_id(self) -> str | None:
        """获取容器 ID"""
        return self._container_id

    def configure_for_testing(
        self,
        session_id: str,
        container_id: str,
    ) -> None:
        """
        配置测试用的模拟会话状态

        此方法仅用于单元测试，不启动真实 Docker 容器。

        Args:
            session_id: 模拟会话 ID
            container_id: 模拟容器 ID
        """
        self._session_id = session_id
        self._container_id = container_id

    @classmethod
    async def cleanup_orphaned_containers(
        cls,
        max_age_seconds: int = 3600,
    ) -> list[str]:
        """
        清理孤儿容器（运行超过指定时间的会话容器）

        Args:
            max_age_seconds: 容器最大存活时间（秒）

        Returns:
            已清理的容器名称列表
        """

        # pylint: disable=too-many-branches
        def run() -> list[str]:
            # 列出所有会话容器
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    f"name={cls.CONTAINER_PREFIX}",
                    "--format",
                    "{{.Names}}\t{{.Status}}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            if result.returncode != 0:
                return []

            cleaned = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("\t")
                if len(parts) < 2:
                    continue

                container_name = parts[0]
                status = parts[1]

                # 解析运行时间（如 "Up 2 hours", "Up 30 minutes"）
                should_cleanup = False
                if "Up" in status:
                    # 检查是否超过最大存活时间
                    if "hour" in status:
                        hours = int(status.split()[1]) if status.split()[1].isdigit() else 1
                        if hours * 3600 >= max_age_seconds:
                            should_cleanup = True
                    elif "minute" in status:
                        minutes = int(status.split()[1]) if status.split()[1].isdigit() else 1
                        if minutes * 60 >= max_age_seconds:
                            should_cleanup = True
                    elif "second" in status:
                        # 秒级别通常不需要清理
                        pass
                    elif "day" in status:
                        # 超过一天肯定要清理
                        should_cleanup = True
                elif "Exited" in status:
                    # 已停止的容器也清理
                    should_cleanup = True

                if should_cleanup:
                    subprocess.run(
                        ["docker", "rm", "-f", container_name],
                        capture_output=True,
                        check=False,
                    )
                    cleaned.append(container_name)
                    logger.info("Cleaned up orphaned container: %s", container_name)

            return cleaned

        return await asyncio.to_thread(run)

    @classmethod
    async def cleanup_all_session_containers(cls) -> list[str]:
        """
        清理所有会话容器（用于重启/关闭时）

        Returns:
            已清理的容器名称列表
        """

        def run() -> list[str]:
            # 列出所有会话容器
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "-aq",
                    "--filter",
                    f"name={cls.CONTAINER_PREFIX}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            if result.returncode != 0 or not result.stdout.strip():
                return []

            container_ids = result.stdout.strip().split("\n")

            # 批量删除
            if container_ids:
                subprocess.run(
                    ["docker", "rm", "-f", *container_ids],
                    capture_output=True,
                    check=False,
                )
                logger.info("Cleaned up %d session containers", len(container_ids))

            return container_ids

        return await asyncio.to_thread(run)

    async def start_session(
        self,
        config: SandboxConfig | None = None,
    ) -> str:
        """
        启动会话容器

        Returns:
            session_id: 会话 ID
        """
        if self._container_id:
            return self._session_id or ""

        config = config or SandboxConfig()
        self._session_id = uuid.uuid4().hex[:12]
        container_name = f"session-{self._session_id}"

        cmd = [
            "docker",
            "run",
            "-d",  # 后台运行
            "--name",
            container_name,
        ]

        # 资源限制
        cmd.extend(["--memory", f"{config.memory_limit_mb}m"])
        cmd.extend(["--cpus", str(config.cpu_limit)])

        # 设置 UTF-8 环境变量，确保容器内输出正确的编码
        cmd.extend(["-e", "LANG=C.UTF-8"])
        cmd.extend(["-e", "LC_ALL=C.UTF-8"])

        # 网络配置
        if not config.network_enabled:
            cmd.extend(["--network", "none"])

        # 持久化卷
        if self.workspace_path:
            cmd.extend(["-v", f"{self.workspace_path}:{self.container_workspace}:rw"])

        # 工作目录
        cmd.extend(["-w", self.container_workspace])

        # 镜像和保持运行的命令
        cmd.extend([self.image, "tail", "-f", "/dev/null"])

        logger.info("Starting session container: %s", container_name)

        def run() -> tuple[str, str]:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            return result.stdout.strip(), result.stderr.strip()

        stdout, stderr = await asyncio.to_thread(run)

        if stderr and "Error" in stderr:
            logger.error("Failed to start session: %s", stderr)
            raise RuntimeError(f"Failed to start session container: {stderr}")

        self._container_id = stdout[:12] if stdout else container_name
        self._last_activity = time.time()
        logger.info("Session started: %s (container: %s)", self._session_id, self._container_id)
        return self._session_id

    def is_expired(self) -> bool:
        """检查会话是否已过期"""
        if not self._last_activity:
            return False
        return (time.time() - self._last_activity) > self.max_idle_seconds

    async def stop_session(self) -> None:
        """停止并清理会话容器"""
        if not self._container_id:
            return

        container_name = f"session-{self._session_id}"
        logger.info("Stopping session: %s", self._session_id)

        def run() -> None:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                check=False,
            )

        await asyncio.to_thread(run)
        self._container_id = None
        self._session_id = None

    async def execute_python(
        self,
        code: str,
        config: SandboxConfig | None = None,
    ) -> ExecutionResult:
        """在会话容器中执行 Python 代码"""
        if not self._container_id:
            await self.start_session(config)

        # 将代码写入容器内的临时文件
        escaped_code = code.replace("'", "'\"'\"'")
        write_cmd = f"echo '{escaped_code}' > /tmp/script.py"
        await self._exec_in_container(write_cmd, config)

        # 执行代码
        return await self._exec_in_container("python /tmp/script.py", config)

    async def execute_shell(
        self,
        command: str,
        config: SandboxConfig | None = None,
    ) -> ExecutionResult:
        """在会话容器中执行 Shell 命令"""
        if not self._container_id:
            await self.start_session(config)

        return await self._exec_in_container(command, config)

    async def _exec_in_container(
        self,
        command: str,
        config: SandboxConfig | None = None,
    ) -> ExecutionResult:
        """在运行中的容器内执行命令"""
        config = config or SandboxConfig()
        container_name = f"session-{self._session_id}"

        # 更新最后活动时间
        self._last_activity = time.time()

        cmd = [
            "docker",
            "exec",
            "-w",
            self.container_workspace,
            "-e",
            "LANG=C.UTF-8",
            "-e",
            "LC_ALL=C.UTF-8",
            container_name,
            "sh",
            "-c",
            command,
        ]

        start_time = time.time()

        def run() -> tuple[int, str, str, str | None]:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=config.timeout_seconds,
                    text=True,
                    encoding="utf-8",
                    errors="replace",  # 替换无法解码的字符，避免崩溃
                    check=False,
                )
                return (result.returncode, result.stdout, result.stderr, None)
            except subprocess.TimeoutExpired:
                return (-1, "", "", f"Execution timed out after {config.timeout_seconds} seconds")
            except Exception as e:
                return (-1, "", "", str(e))

        returncode, stdout, stderr, error = await asyncio.to_thread(run)
        duration_ms = int((time.time() - start_time) * 1000)

        return ExecutionResult(
            success=returncode == 0 and error is None,
            stdout=stdout.strip(),
            stderr=stderr.strip(),
            exit_code=returncode,
            duration_ms=duration_ms,
            error=error,
        )

    async def __aenter__(self) -> "SessionDockerExecutor":
        """支持 async with 语法"""
        await self.start_session()
        return self

    async def __aexit__(self, *_: object) -> None:
        """退出时自动清理"""
        await self.stop_session()

    def __del__(self) -> None:
        """析构时尝试清理（同步方式，尽力而为）"""
        if self._container_id and self._session_id:
            container_name = f"session-{self._session_id}"
            with contextlib.suppress(Exception):
                subprocess.run(
                    ["docker", "rm", "-f", container_name],
                    capture_output=True,
                    check=False,
                    timeout=5,
                )


class LocalExecutor(SandboxExecutor):
    """
    本地执行器 (仅开发环境)

    警告: 不安全，仅用于开发测试
    """

    def __init__(self, work_dir: str = "./workspace") -> None:
        """
        初始化本地执行器

        Args:
            work_dir: 工作目录
        """
        self.work_dir = work_dir
        # 确保工作目录存在（Windows 上如果目录不存在会导致 subprocess 失败）
        Path(work_dir).mkdir(parents=True, exist_ok=True)

    async def execute_python(
        self,
        code: str,
        config: SandboxConfig | None = None,
    ) -> ExecutionResult:
        """执行 Python 代码 (本地)"""
        config = config or SandboxConfig()

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
            # 使用同步方式执行以兼容 Windows
            result = await self._run_subprocess_sync(
                ["python", code_file],
                config.timeout_seconds,
            )
            return result

        finally:
            Path(code_file).unlink(missing_ok=True)

    async def execute_shell(
        self,
        command: str,
        config: SandboxConfig | None = None,
    ) -> ExecutionResult:
        """执行 Shell 命令 (本地)"""
        config = config or SandboxConfig()
        return await self._run_subprocess_sync(
            command,
            config.timeout_seconds,
            shell=True,
        )

    async def _run_subprocess_sync(
        self,
        cmd: str | list[str],
        timeout: int,
        *,
        shell: bool = False,
    ) -> ExecutionResult:
        """
        在线程池中运行同步子进程

        这种方式在所有平台上都能工作，包括 Windows
        """
        start_time = time.time()

        def run() -> tuple[int, str, str, str | None]:
            try:
                result = subprocess.run(
                    cmd,
                    shell=shell,
                    capture_output=True,
                    timeout=timeout,
                    cwd=self.work_dir,
                    text=True,
                    encoding="utf-8",
                    errors="replace",  # 替换无法解码的字符，避免崩溃
                    check=False,
                )
                return (result.returncode, result.stdout, result.stderr, None)
            except subprocess.TimeoutExpired:
                return (-1, "", "", f"Execution timed out after {timeout} seconds")
            except Exception as e:
                return (-1, "", "", str(e))

        returncode, stdout, stderr, error = await asyncio.to_thread(run)
        duration_ms = int((time.time() - start_time) * 1000)

        return ExecutionResult(
            success=returncode == 0 and error is None,
            stdout=stdout.strip(),
            stderr=stderr.strip(),
            exit_code=returncode,
            duration_ms=duration_ms,
            error=error,
        )
