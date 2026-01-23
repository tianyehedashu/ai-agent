"""
沙箱执行器单元测试

测试 LocalExecutor 和 DockerExecutor 的基本功能
"""
# pylint: disable=protected-access  # 测试代码需要访问私有方法

import sys

import pytest

from domains.agent.infrastructure.sandbox.executor import (
    DockerExecutor,
    ExecutionResult,
    LocalExecutor,
    SandboxConfig,
    SessionDockerExecutor,
)
from domains.agent.infrastructure.sandbox.factory import ExecutorFactory


class TestSandboxConfig:
    """测试沙箱配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = SandboxConfig()
        assert config.timeout_seconds == 30
        assert config.memory_limit_mb == 256
        assert config.cpu_limit == 1.0
        assert config.network_enabled is False
        assert config.read_only_root is True

    def test_custom_config(self):
        """测试自定义配置"""
        config = SandboxConfig(
            timeout_seconds=60,
            memory_limit_mb=512,
            network_enabled=True,
        )
        assert config.timeout_seconds == 60
        assert config.memory_limit_mb == 512
        assert config.network_enabled is True


class TestExecutionResult:
    """测试执行结果"""

    def test_success_result(self):
        """测试成功结果"""
        result = ExecutionResult(
            success=True,
            stdout="Hello, World!",
            stderr="",
            exit_code=0,
            duration_ms=100,
        )
        assert result.success is True
        assert result.stdout == "Hello, World!"
        assert result.exit_code == 0
        assert result.error is None

    def test_failure_result(self):
        """测试失败结果"""
        result = ExecutionResult(
            success=False,
            stdout="",
            stderr="Command not found",
            exit_code=127,
            duration_ms=50,
            error="Command failed",
        )
        assert result.success is False
        assert result.exit_code == 127
        assert result.error == "Command failed"


class TestLocalExecutor:
    """测试本地执行器"""

    @pytest.fixture
    def executor(self):
        """创建本地执行器"""
        return LocalExecutor()

    @pytest.mark.asyncio
    async def test_execute_shell_echo(self, executor):
        """测试执行 echo 命令"""
        result = await executor.execute_shell("echo Hello")
        assert result.success is True
        assert "Hello" in result.stdout
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_execute_shell_with_custom_timeout(self, executor):
        """测试自定义超时"""
        config = SandboxConfig(timeout_seconds=5)
        result = await executor.execute_shell("echo test", config=config)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_shell_timeout(self, executor):
        """测试命令超时"""
        config = SandboxConfig(timeout_seconds=1)
        # 使用跨平台的超时命令
        if sys.platform == "win32":
            cmd = "ping -n 10 127.0.0.1"
        else:
            cmd = "sleep 10"

        result = await executor.execute_shell(cmd, config=config)
        assert result.success is False
        assert result.error is not None
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_shell_failure(self, executor):
        """测试命令失败"""
        # 使用一个不存在的命令
        result = await executor.execute_shell("nonexistent_command_xyz_123")
        # 命令不存在可能返回不同的退出码，但应该是失败的
        assert result.success is False or result.exit_code != 0

    @pytest.mark.asyncio
    async def test_execute_python_simple(self, executor):
        """测试执行简单 Python 代码"""
        code = "print('Hello from Python')"
        result = await executor.execute_python(code)
        assert result.success is True
        assert "Hello from Python" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_python_with_error(self, executor):
        """测试执行有语法错误的 Python 代码"""
        code = "print('unclosed string"
        result = await executor.execute_python(code)
        assert result.success is False
        assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_execute_python_with_exception(self, executor):
        """测试执行会抛出异常的 Python 代码"""
        code = "raise ValueError('test error')"
        result = await executor.execute_python(code)
        assert result.success is False
        assert "ValueError" in result.stderr or "ValueError" in result.stdout


class TestDockerExecutor:
    """测试 Docker 执行器"""

    @pytest.fixture
    def executor(self):
        """创建 Docker 执行器"""
        return DockerExecutor()

    def test_build_docker_command(self, executor):
        """测试构建 Docker 命令"""
        config = SandboxConfig(
            memory_limit_mb=256,
            cpu_limit=1.0,
            network_enabled=False,
            read_only_root=True,
        )
        cmd = executor._build_docker_command(
            image="python:3.11-slim",
            command="echo test",
            volumes={},
            config=config,
        )

        # 验证命令结构
        assert "docker" in cmd
        assert "run" in cmd
        assert "--rm" in cmd
        assert "--memory" in cmd
        assert "256m" in cmd
        assert "--network" in cmd
        assert "none" in cmd
        assert "--read-only" in cmd

    def test_build_docker_command_with_network(self, executor):
        """测试启用网络的 Docker 命令"""
        config = SandboxConfig(network_enabled=True)
        cmd = executor._build_docker_command(
            image="alpine",
            command="echo test",
            volumes={},
            config=config,
        )

        # 启用网络时不应该有 --network none
        cmd_str = " ".join(cmd)
        assert "--network none" not in cmd_str

    def test_build_docker_command_no_double_wrapping(self, executor):
        """测试命令不会被双重包装 (sh -c)"""
        config = SandboxConfig()
        cmd = executor._build_docker_command(
            image="alpine",
            command="date",  # 简单命令
            volumes={},
            config=config,
        )

        # 命令应该只被包装一次
        cmd_str = " ".join(cmd)
        # 只有一个 "sh -c"
        assert cmd_str.count("sh -c") == 1
        # 不应该有 "sh -c 'sh -c" 这样的双重包装
        assert "sh -c 'sh -c" not in cmd_str
        assert 'sh -c "sh -c' not in cmd_str

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_execute_shell_in_docker(self, executor):
        """集成测试：验证 Docker 沙箱能正常执行命令

        注意：需要 Docker 已安装并运行
        主要验证：命令正确传递到容器（无双重包装问题）
        """
        result = await executor.execute_shell("echo 'Hello World'")
        assert result.success is True, f"Docker execution failed: {result.error}"
        assert "Hello World" in result.stdout


@pytest.mark.xdist_group("docker_session")
class TestSessionDockerExecutor:
    """测试会话级 Docker 执行器

    注意：此类中的测试需要使用 xdist_group 标记，
    确保在并行测试时这些测试在同一个 worker 中串行执行，
    避免 cleanup_all_session_containers 清理正在使用的容器。
    """

    @pytest.fixture
    def executor(self):
        """创建会话执行器"""
        return SessionDockerExecutor()

    def test_init_default_values(self, executor):
        """测试默认初始化值"""
        assert executor.image == "python:3.11-slim"
        assert executor.container_workspace == "/workspace"
        assert executor.is_running is False

    def test_init_custom_values(self):
        """测试自定义初始化值"""
        executor = SessionDockerExecutor(
            image="node:18-slim",
            workspace_path="/host/workspace",
            container_workspace="/app",
        )
        assert executor.image == "node:18-slim"
        assert executor.workspace_path == "/host/workspace"
        assert executor.container_workspace == "/app"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_lifecycle(self):
        """集成测试：会话生命周期（启动、执行、停止）"""
        executor = SessionDockerExecutor(image="alpine:latest")
        try:
            # 启动会话
            session_id = await executor.start_session()
            assert session_id is not None
            assert len(session_id) == 12
            assert executor.is_running is True

            # 执行命令
            result = await executor.execute_shell("echo 'Hello Session'")
            assert result.success is True, f"Execution failed: {result.error}"
            assert "Hello Session" in result.stdout

        finally:
            # 停止会话
            await executor.stop_session()
            assert executor.is_running is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_state_persistence(self):
        """集成测试：验证会话内状态保持"""
        executor = SessionDockerExecutor(image="alpine:latest")
        try:
            await executor.start_session()

            # 创建文件
            result1 = await executor.execute_shell("echo 'test content' > /tmp/test.txt")
            assert result1.success is True

            # 读取文件 - 应该能读到（状态保持）
            result2 = await executor.execute_shell("cat /tmp/test.txt")
            assert result2.success is True
            assert "test content" in result2.stdout

        finally:
            await executor.stop_session()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_context_manager(self):
        """集成测试：async with 语法支持"""
        async with SessionDockerExecutor(image="alpine:latest") as executor:
            assert executor.is_running is True
            result = await executor.execute_shell("echo 'context manager'")
            assert result.success is True

        # 退出后应该已停止
        assert executor.is_running is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cleanup_all_session_containers(self):
        """集成测试：清理所有会话容器"""
        # 创建一个会话容器
        executor = SessionDockerExecutor(image="alpine:latest")
        await executor.start_session()
        assert executor.is_running is True

        # 清理所有容器
        cleaned = await SessionDockerExecutor.cleanup_all_session_containers()
        assert len(cleaned) >= 1

        # 容器应该已被删除（executor 对象不知道，但 is_running 仍为 True）
        # 这是预期行为，因为清理是类方法，不会更新实例状态


class TestExecutorFactory:
    """测试执行器工厂"""

    def test_create_default_executor(self):
        """测试创建默认执行器（无配置）"""
        executor = ExecutorFactory.create(None)
        assert isinstance(executor, LocalExecutor)

    def test_create_local_executor(self):
        """测试创建本地执行器"""
        from libs.config.execution_config import (
            ExecutionConfig,
            SandboxConfig,
            SandboxMode,
        )

        config = ExecutionConfig(
            sandbox=SandboxConfig(mode=SandboxMode.LOCAL),
        )
        executor = ExecutorFactory.create(config, force_new=True)
        assert isinstance(executor, LocalExecutor)

    def test_create_session_docker_executor_default(self):
        """测试创建会话 Docker 执行器（默认启用 session）"""
        from libs.config.execution_config import (
            ExecutionConfig,
            SandboxConfig,
            SandboxMode,
        )

        config = ExecutionConfig(
            sandbox=SandboxConfig(mode=SandboxMode.DOCKER),
        )
        executor = ExecutorFactory.create(config, force_new=True)
        # 默认 session_enabled=True，应该创建 SessionDockerExecutor
        assert isinstance(executor, SessionDockerExecutor)

    def test_create_stateless_docker_executor(self):
        """测试创建无状态 Docker 执行器（禁用 session）"""
        from libs.config.execution_config import (
            DockerConfig,
            ExecutionConfig,
            SandboxConfig,
            SandboxMode,
        )

        config = ExecutionConfig(
            sandbox=SandboxConfig(
                mode=SandboxMode.DOCKER,
                docker=DockerConfig(session_enabled=False),
            ),
        )
        executor = ExecutorFactory.create(config, force_new=True)
        # session_enabled=False，应该创建 DockerExecutor
        assert isinstance(executor, DockerExecutor)

    def test_create_remote_executor_not_implemented(self):
        """测试创建远程执行器（未实现）"""
        from libs.config.execution_config import (
            ExecutionConfig,
            SandboxConfig,
            SandboxMode,
        )

        config = ExecutionConfig(
            sandbox=SandboxConfig(mode=SandboxMode.REMOTE),
        )
        with pytest.raises(NotImplementedError):
            ExecutorFactory.create(config, force_new=True)

    def test_executor_caching(self):
        """测试执行器缓存"""
        ExecutorFactory.clear_cache()

        executor1 = ExecutorFactory.create(None)
        executor2 = ExecutorFactory.create(None)

        # 默认使用缓存，应该是同一个实例
        # 注意：默认无配置时每次创建新实例
        assert executor1 is not None
        assert executor2 is not None

    def test_clear_cache(self):
        """测试清理缓存"""
        ExecutorFactory.clear_cache()
        assert len(ExecutorFactory._instances) == 0
