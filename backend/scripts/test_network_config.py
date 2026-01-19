#!/usr/bin/env python3
"""
测试沙箱网络配置

验证不同环境模板的网络配置是否正常工作
"""

import asyncio
from pathlib import Path
import sys

# 添加项目根目录到路径（必须在导入项目模块前执行）
sys.path.insert(0, str(Path(__file__).parent.parent))

# pylint: disable=wrong-import-position  # sys.path.insert 必须在前
from core.config import get_execution_config_service
from core.config.execution_config import (
    ExecutionConfig,
    NetworkConfig,
)
from core.config.execution_config import (
    SandboxConfig as SandboxCfg,
)
from core.sandbox.executor import SandboxConfig
from core.sandbox.factory import ExecutorFactory


async def test_network_disabled():
    """测试网络禁用配置"""
    print("\n" + "=" * 60)
    print("测试 1: 网络禁用（默认安全配置）")
    print("=" * 60)

    # 创建禁用网络的配置
    config = ExecutionConfig(sandbox=SandboxCfg(network=NetworkConfig(enabled=False)))

    executor = ExecutorFactory.create(config, force_new=True)

    code = """
import socket
try:
    socket.create_connection(("pypi.org", 80), timeout=2)
    print("❌ 意外：网络可用（应该被禁用）")
except Exception as e:
    print(f"✅ 预期：网络已禁用 - {type(e).__name__}")
"""

    result = await executor.execute_python(
        code,
        config=SandboxConfig(
            timeout_seconds=10,
            network_enabled=False,
        ),
    )

    print(result.stdout)
    if result.stderr:
        print(f"stderr: {result.stderr}")

    return "网络已禁用" in result.stdout or "Network" in result.stderr


async def test_network_enabled():
    """测试网络启用配置"""
    print("\n" + "=" * 60)
    print("测试 2: 网络启用")
    print("=" * 60)

    # 使用网络启用配置
    config = ExecutionConfig(
        sandbox=SandboxCfg(
            network=NetworkConfig(
                enabled=True,
                allowed_hosts=["pypi.org", "httpbin.org"],
            )
        )
    )

    executor = ExecutorFactory.create(config, force_new=True)

    code = """
import socket
import sys

print("Python version:", sys.version)

# 测试 DNS 解析
try:
    import socket
    ip = socket.gethostbyname("pypi.org")
    print(f"✅ DNS 解析成功: pypi.org -> {ip}")
except Exception as e:
    print(f"❌ DNS 解析失败: {e}")

# 测试网络连接
try:
    sock = socket.create_connection(("pypi.org", 80), timeout=5)
    sock.close()
    print("✅ 网络连接成功: pypi.org:80")
except Exception as e:
    print(f"❌ 网络连接失败: {e}")
"""

    result = await executor.execute_python(
        code,
        config=SandboxConfig(
            timeout_seconds=15,
            network_enabled=True,
        ),
    )

    print(result.stdout)
    if result.stderr:
        print(f"stderr: {result.stderr}")

    return "网络连接成功" in result.stdout or "DNS 解析成功" in result.stdout


async def test_environment_template(template_name: str):
    """测试环境模板"""
    print("\n" + "=" * 60)
    print(f"测试 3: 环境模板 '{template_name}'")
    print("=" * 60)

    try:
        # 加载环境模板
        service = get_execution_config_service()
        config = service.get_template(template_name)

        if not config:
            raise ValueError(f"Template '{template_name}' not found")

        print(f"网络启用: {config.sandbox.network.enabled}")
        print(f"白名单主机: {config.sandbox.network.allowed_hosts or '(所有主机)'}")
        print(f"内存限制: {config.sandbox.resources.memory_limit}")
        print(f"CPU 限制: {config.sandbox.resources.cpu_limit}")
        print(f"超时时间: {config.sandbox.timeout_seconds}秒")

        # 创建执行器并测试
        executor = ExecutorFactory.create(config, force_new=True)

        code = """
import socket
try:
    ip = socket.gethostbyname("pypi.org")
    print(f"✅ 网络可用: pypi.org -> {ip}")
except Exception as e:
    print(f"❌ 网络不可用: {type(e).__name__}")
"""

        result = await executor.execute_python(
            code,
            config=SandboxConfig(
                timeout_seconds=config.sandbox.timeout_seconds,
                network_enabled=config.sandbox.network.enabled,
            ),
        )

        print("\n执行结果:")
        print(result.stdout)
        if result.stderr:
            print(f"stderr: {result.stderr}")

        return True
    except Exception as e:
        print(f"❌ 模板加载失败: {e}")
        return False


async def test_shell_network():
    """测试 Shell 命令网络访问"""
    print("\n" + "=" * 60)
    print("测试 4: Shell 命令网络访问")
    print("=" * 60)

    config = ExecutionConfig(sandbox=SandboxCfg(network=NetworkConfig(enabled=True)))

    executor = ExecutorFactory.create(config, force_new=True)

    # 测试 ping 或 wget
    command = "wget -q -O - --timeout=5 http://httpbin.org/ip || echo 'Network request failed'"

    result = await executor.execute_shell(
        command,
        config=SandboxConfig(
            timeout_seconds=10,
            network_enabled=True,
        ),
    )

    print(f"命令: {command}")
    print(f"输出: {result.stdout}")
    if result.stderr:
        print(f"错误: {result.stderr}")

    return result.exit_code == 0


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("沙箱网络配置测试")
    print("=" * 60)

    results = []

    # 测试 1: 网络禁用
    try:
        result = await test_network_disabled()
        results.append(("网络禁用", result))
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results.append(("网络禁用", False))

    # 测试 2: 网络启用
    try:
        result = await test_network_enabled()
        results.append(("网络启用", result))
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results.append(("网络启用", False))

    # 测试 3: 环境模板
    templates = ["docker-dev", "network-enabled", "network-restricted"]
    for template in templates:
        try:
            result = await test_environment_template(template)
            results.append((f"模板: {template}", result))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append((f"模板: {template}", False))

    # 测试 4: Shell 网络
    try:
        result = await test_shell_network()
        results.append(("Shell 网络", result))
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        results.append(("Shell 网络", False))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(1 for _, success in results if success)
    print(f"\n总计: {passed}/{total} 通过")

    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
