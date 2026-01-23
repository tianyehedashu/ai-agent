"""测试工具注册表 - 诊断脚本"""

import asyncio
import sys
import traceback

from domains.runtime.infrastructure.tools.base import BaseTool
from domains.runtime.infrastructure.tools.registry import ToolRegistry


async def check_asyncio_subprocess():
    """检查 asyncio subprocess 是否可用"""
    print("\n=== 检查 asyncio subprocess 可用性 ===")
    print(f"Python 版本: {sys.version}")
    print(f"平台: {sys.platform}")

    try:
        process = await asyncio.create_subprocess_shell(
            "echo test",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await process.communicate()
        print("asyncio.create_subprocess_shell: 可用")
        print(f"  stdout: {stdout.decode().strip()}")
        return True
    except NotImplementedError as e:
        print(f"asyncio.create_subprocess_shell: 不可用 (NotImplementedError: {e})")
        return False
    except Exception as e:
        print(f"asyncio.create_subprocess_shell: 异常 ({type(e).__name__}: {e})")
        return False


async def main():
    # 首先检查 asyncio subprocess
    subprocess_available = await check_asyncio_subprocess()

    if not subprocess_available:
        print("\n⚠️ asyncio subprocess 不可用，这可能是 run_shell 失败的原因！")
        return

    tr = ToolRegistry()

    # 列出所有工具
    print("\n=== 已注册的工具 ===")
    for tool in tr.list_all():
        print(f"  - {tool.name}: {type(tool).__name__}")

    # 测试 run_shell
    tool = tr.get("run_shell")
    if tool:
        print("\n=== run_shell 工具详情 ===")
        print(f"  类型: {type(tool).__name__}")
        print(f"  描述: {tool.description}")
        print(f"  execute 方法: {tool.execute}")
        print(f"  execute 是否为协程: {asyncio.iscoroutinefunction(tool.execute)}")

        # 检查是否是基类的抽象方法
        if tool.execute == BaseTool.execute:
            print("  ⚠️ 警告: execute 是基类的抽象方法，可能会抛出 NotImplementedError!")

        # 尝试执行不同的命令
        commands = [
            "echo Hello World",  # 简单回显
        ]

        # 根据平台选择命令
        if sys.platform == "win32":
            commands.extend(["date /t", "time /t"])
        else:
            commands.extend(["date", "pwd"])

        for cmd in commands:
            print(f"\n尝试执行 '{cmd}'...")
            try:
                result = await tr.execute("run_shell", command=cmd)
                print(f"  成功: {result.success}")
                print(f"  输出: {result.output}")
                print(f"  错误: {result.error}")
            except NotImplementedError as e:
                print(f"  ⚠️ NotImplementedError: {e}")
                traceback.print_exc()
            except Exception as e:
                print(f"  异常: {type(e).__name__}: {e}")
                traceback.print_exc()
    else:
        print("⚠️ run_shell 工具未找到!")


if __name__ == "__main__":
    asyncio.run(main())
