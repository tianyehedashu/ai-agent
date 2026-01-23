"""
代码工具沙箱集成测试

测试 RunShellTool 和 RunPythonTool 与沙箱执行器的集成
"""

import sys
import tempfile

import pytest

from shared.infrastructure.config.execution_config import (
    ExecutionConfig,
    ResourceConfig,
    SandboxConfig,
    SandboxMode,
    ShellConfig,
)
from domains.runtime.infrastructure.sandbox.factory import ExecutorFactory
from domains.runtime.infrastructure.tools.code_tools import RunPythonTool, RunShellTool
from domains.runtime.infrastructure.tools.registry import ConfiguredToolRegistry


class TestRunShellToolWithSandbox:
    """测试 RunShellTool 与沙箱集成"""

    @pytest.fixture
    def local_config(self):
        """创建本地模式配置"""
        # 使用临时目录作为工作目录，确保 Windows 和 Linux 都可用
        work_dir = tempfile.gettempdir()
        return ExecutionConfig(
            sandbox=SandboxConfig(
                mode=SandboxMode.LOCAL,
                timeout_seconds=30,
            ),
            shell=ShellConfig(work_dir=work_dir),
        )

    @pytest.fixture
    def docker_config(self):
        """创建 Docker 模式配置"""
        return ExecutionConfig(
            sandbox=SandboxConfig(
                mode=SandboxMode.DOCKER,
                timeout_seconds=30,
                resources=ResourceConfig(memory_limit="256m", cpu_limit=1.0),
            ),
        )

    @pytest.mark.asyncio
    async def test_shell_tool_with_local_executor(self, local_config):
        """测试本地模式下的 Shell 工具"""
        # 注入配置
        RunShellTool.execution_config = local_config
        tool = RunShellTool()

        result = await tool.execute(command="echo Hello from sandbox")

        assert result.success is True
        assert "Hello from sandbox" in result.output

    @pytest.mark.asyncio
    async def test_shell_tool_without_config(self):
        """测试无配置时的 Shell 工具（应使用本地执行器）"""
        RunShellTool.execution_config = None
        tool = RunShellTool()

        result = await tool.execute(command="echo test")

        assert result.success is True
        assert "test" in result.output

    @pytest.mark.asyncio
    async def test_shell_tool_timeout(self, local_config):
        """测试 Shell 工具超时处理"""
        RunShellTool.execution_config = local_config
        tool = RunShellTool()

        # 使用跨平台的超时命令
        if sys.platform == "win32":
            cmd = "ping -n 10 127.0.0.1"
        else:
            cmd = "sleep 10"

        result = await tool.execute(command=cmd, timeout=1)

        assert result.success is False
        assert result.error is not None
        assert "timed out" in result.error.lower()


class TestRunPythonToolWithSandbox:
    """测试 RunPythonTool 与沙箱集成"""

    @pytest.fixture
    def local_config(self):
        """创建本地模式配置"""
        work_dir = tempfile.gettempdir()
        return ExecutionConfig(
            sandbox=SandboxConfig(
                mode=SandboxMode.LOCAL,
                timeout_seconds=30,
            ),
            shell=ShellConfig(work_dir=work_dir),
        )

    @pytest.mark.asyncio
    async def test_python_tool_with_local_executor(self, local_config):
        """测试本地模式下的 Python 工具"""
        RunPythonTool.execution_config = local_config
        tool = RunPythonTool()

        result = await tool.execute(code="print('Hello from Python sandbox')")

        assert result.success is True
        assert "Hello from Python sandbox" in result.output

    @pytest.mark.asyncio
    async def test_python_tool_without_config(self):
        """测试无配置时的 Python 工具"""
        RunPythonTool.execution_config = None
        tool = RunPythonTool()

        result = await tool.execute(code="print(1 + 1)")

        assert result.success is True
        assert "2" in result.output

    @pytest.mark.asyncio
    async def test_python_tool_with_error(self, local_config):
        """测试 Python 工具错误处理"""
        RunPythonTool.execution_config = local_config
        tool = RunPythonTool()

        result = await tool.execute(code="raise ValueError('test error')")

        assert result.success is False
        assert "ValueError" in (result.error or "") or "ValueError" in result.output


class TestConfiguredToolRegistry:
    """测试配置化的工具注册表"""

    @pytest.fixture
    def config(self):
        """创建测试配置"""
        work_dir = tempfile.gettempdir()
        return ExecutionConfig(
            sandbox=SandboxConfig(
                mode=SandboxMode.LOCAL,
                timeout_seconds=60,
            ),
            shell=ShellConfig(work_dir=work_dir),
        )

    def test_execution_config_injection(self, config):
        """测试执行配置注入到工具"""
        registry = ConfiguredToolRegistry(config)

        # 获取工具 - 使用 _ 前缀表示有意不使用变量
        _run_shell = registry.get("run_shell")
        _run_python = registry.get("run_python")

        # 验证配置已注入
        assert RunShellTool.execution_config is config
        assert RunPythonTool.execution_config is config

    @pytest.mark.asyncio
    async def test_execute_shell_via_registry(self, config):
        """测试通过注册表执行 Shell 命令"""
        registry = ConfiguredToolRegistry(config)

        result = await registry.execute("run_shell", command="echo registry test")

        assert result.success is True
        assert "registry test" in result.output

    @pytest.mark.asyncio
    async def test_execute_python_via_registry(self, config):
        """测试通过注册表执行 Python 代码"""
        registry = ConfiguredToolRegistry(config)

        result = await registry.execute("run_python", code="print('registry python')")

        assert result.success is True
        assert "registry python" in result.output


class TestSandboxModeSelection:
    """测试沙箱模式选择"""

    def test_local_mode_uses_local_executor(self):
        """测试本地模式使用本地执行器"""
        from domains.runtime.infrastructure.sandbox.executor import LocalExecutor

        config = ExecutionConfig(
            sandbox=SandboxConfig(mode=SandboxMode.LOCAL),
        )
        executor = ExecutorFactory.create(config, force_new=True)

        assert isinstance(executor, LocalExecutor)

    def test_docker_mode_uses_session_executor(self):
        """测试 Docker 模式使用会话执行器（默认启用 session）"""
        from domains.runtime.infrastructure.sandbox.executor import SessionDockerExecutor

        config = ExecutionConfig(
            sandbox=SandboxConfig(mode=SandboxMode.DOCKER),
        )
        executor = ExecutorFactory.create(config, force_new=True)

        # 默认 session_enabled=True，应该创建 SessionDockerExecutor
        assert isinstance(executor, SessionDockerExecutor)

    def test_remote_mode_not_implemented(self):
        """测试远程模式未实现"""
        config = ExecutionConfig(
            sandbox=SandboxConfig(mode=SandboxMode.REMOTE),
        )

        with pytest.raises(NotImplementedError):
            ExecutorFactory.create(config, force_new=True)


class TestMemoryLimitParsing:
    """测试内存限制解析"""

    def test_parse_megabytes(self):
        """测试解析 MB 单位"""
        from domains.runtime.infrastructure.tools.code_tools import _parse_memory_limit

        assert _parse_memory_limit("256m") == 256
        assert _parse_memory_limit("512M") == 512
        assert _parse_memory_limit("1024m") == 1024

    def test_parse_gigabytes(self):
        """测试解析 GB 单位"""
        from domains.runtime.infrastructure.tools.code_tools import _parse_memory_limit

        assert _parse_memory_limit("1g") == 1024
        assert _parse_memory_limit("2G") == 2048
        assert _parse_memory_limit("0.5g") == 512

    def test_parse_kilobytes(self):
        """测试解析 KB 单位"""
        from domains.runtime.infrastructure.tools.code_tools import _parse_memory_limit

        assert _parse_memory_limit("1024k") == 1
        assert _parse_memory_limit("2048k") == 2

    def test_parse_plain_number(self):
        """测试解析纯数字"""
        from domains.runtime.infrastructure.tools.code_tools import _parse_memory_limit

        assert _parse_memory_limit("256") == 256
        assert _parse_memory_limit("512") == 512
