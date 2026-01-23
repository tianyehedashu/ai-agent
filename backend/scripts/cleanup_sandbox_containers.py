#!/usr/bin/env python3
"""
沙箱容器清理脚本

一键清理所有沙箱容器（仅删除以 session- 开头的容器）

安全保护：
- 只删除以 "session-" 开头的容器（精确前缀匹配）
- 不会误删其他 Docker 容器（如 postgres、redis、qdrant 等）
- 在列出和删除时都有安全检查

用法:
    python scripts/cleanup_sandbox_containers.py              # 交互式清理
    python scripts/cleanup_sandbox_containers.py --force       # 强制清理（不询问）
    python scripts/cleanup_sandbox_containers.py --dry-run      # 仅显示，不实际删除
    python scripts/cleanup_sandbox_containers.py --all          # 清理所有容器（包括运行中的）
"""

import argparse
import asyncio
import io
from pathlib import Path
import subprocess
import sys

from domains.agent.infrastructure.sandbox.executor import SessionDockerExecutor
from utils.logging import get_logger

# 设置标准输出编码为 UTF-8（Windows 兼容）
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 添加项目根目录到路径（必须在导入项目模块之前）
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


logger = get_logger(__name__)

CONTAINER_PREFIX = "session-"


def list_containers(include_running: bool = True) -> list[str]:
    """
    列出所有沙箱容器（仅匹配以 session- 开头的容器）

    Args:
        include_running: 是否包含运行中的容器

    Returns:
        容器名称列表（仅包含以 session- 开头的容器）
    """
    # 使用 Docker filter 列出所有容器，然后过滤出以 session- 开头的
    # 注意: Docker 的 name filter 是部分匹配，所以我们需要手动过滤确保精确匹配
    cmd = ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"]
    if not include_running:
        cmd.extend(["--filter", "status=exited"])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        logger.warning("Failed to list containers: %s", result.stderr)
        return []

    # 过滤出以 session- 开头的容器（精确匹配前缀）
    containers = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        # 格式: "容器名\t状态"
        parts = line.split("\t", 1)
        container_name = parts[0].strip()
        # 只添加以 session- 开头的容器（精确前缀匹配）
        if container_name.startswith(CONTAINER_PREFIX):
            containers.append(container_name)

    return containers


def get_container_info(container_name: str) -> dict[str, str]:
    """
    获取容器信息

    Args:
        container_name: 容器名称

    Returns:
        容器信息字典
    """
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Status}}\t{{.State.StartedAt}}",
            container_name,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        return {"status": "unknown", "started_at": ""}

    parts = result.stdout.strip().split("\t")
    return {
        "status": parts[0] if len(parts) > 0 else "unknown",
        "started_at": parts[1] if len(parts) > 1 else "",
    }


async def cleanup_containers(container_names: list[str], force: bool = False) -> list[str]:
    """
    清理容器（仅删除以 session- 开头的容器，安全保护）

    Args:
        container_names: 容器名称列表
        force: 是否强制删除（包括运行中的容器）

    Returns:
        已清理的容器名称列表
    """
    if not container_names:
        return []

    def run() -> list[str]:
        cleaned = []
        for container_name in container_names:
            # 安全检查：只删除以 session- 开头的容器
            if not container_name.startswith(CONTAINER_PREFIX):
                logger.warning(
                    "跳过非沙箱容器（安全保护）: %s (必须以 %s 开头）",
                    container_name,
                    CONTAINER_PREFIX,
                )
                continue
            cmd = ["docker", "rm"]
            if force:
                cmd.append("-f")  # 强制删除运行中的容器
            cmd.append(container_name)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            if result.returncode == 0:
                cleaned.append(container_name)
                logger.info("Cleaned up container: %s", container_name)
            else:
                logger.warning("Failed to cleanup container %s: %s", container_name, result.stderr)

        return cleaned

    return await asyncio.to_thread(run)


async def cleanup_all_using_class_method() -> list[str]:
    """
    使用 SessionDockerExecutor 的类方法清理所有容器

    Returns:
        已清理的容器 ID 列表
    """
    return await SessionDockerExecutor.cleanup_all_session_containers()


def print_container_list(containers: list[str], title: str = "沙箱容器列表") -> None:
    """打印容器列表"""
    if not containers:
        print(f"\n{title}: 无")
        return

    print(f"\n{title} ({len(containers)} 个):")
    print("-" * 80)
    for i, container_name in enumerate(containers, 1):
        info = get_container_info(container_name)
        status_icon = "🟢" if info["status"] == "running" else "🔴"
        print(f"{i:3d}. {status_icon} {container_name:40s} [{info['status']:10s}]")
    print("-" * 80)


async def main() -> int:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="清理沙箱容器（session-* 前缀）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制清理（不询问确认，包括运行中的容器）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅显示要清理的容器，不实际删除",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="清理所有容器（包括运行中的），等同于 --force",
    )
    parser.add_argument(
        "--stopped-only",
        action="store_true",
        help="仅清理已停止的容器",
    )
    parser.add_argument(
        "--use-class-method",
        action="store_true",
        help="使用 SessionDockerExecutor.cleanup_all_session_containers() 方法清理",
    )

    args = parser.parse_args()

    # 如果指定了 --all，自动启用 --force
    if args.all:
        args.force = True

    print("=" * 80)
    print("沙箱容器清理工具")
    print("=" * 80)

    # 列出所有容器
    all_containers = list_containers(include_running=True)
    if not all_containers:
        print("\n✅ 没有找到沙箱容器，无需清理。")
        return 0

    # 根据选项过滤容器
    if args.stopped_only:
        stopped_containers = list_containers(include_running=False)
        containers_to_cleanup = stopped_containers
        print(f"\n📋 仅清理已停止的容器 ({len(containers_to_cleanup)} 个)")
    else:
        containers_to_cleanup = all_containers
        print(f"\n📋 清理所有沙箱容器 ({len(containers_to_cleanup)} 个)")

    # 显示容器列表
    print_container_list(containers_to_cleanup, "待清理的容器")

    # 检查是否有运行中的容器
    running_containers = [
        c for c in containers_to_cleanup if get_container_info(c)["status"] == "running"
    ]
    if running_containers and not args.force:
        print(f"\n⚠️  警告: 发现 {len(running_containers)} 个运行中的容器:")
        for container in running_containers:
            print(f"    - {container}")
        print("\n💡 提示: 使用 --force 或 --all 可以强制删除运行中的容器")

    # 如果是 dry-run，只显示不删除
    if args.dry_run:
        print("\n🔍 预览模式（--dry-run）: 不会实际删除容器")
        return 0

    # 确认删除
    if not args.force:
        print("\n❓ 确认删除以上容器? [y/N]: ", end="", flush=True)
        try:
            response = input().strip().lower()
            if response not in ("y", "yes"):
                print("❌ 已取消清理操作")
                return 1
        except (EOFError, KeyboardInterrupt):
            print("\n❌ 已取消清理操作")
            return 1

    # 执行清理
    print("\n🧹 开始清理容器...")
    if args.use_class_method:
        print("📦 使用 SessionDockerExecutor.cleanup_all_session_containers() 方法")
        cleaned = await cleanup_all_using_class_method()
    else:
        cleaned = await cleanup_containers(containers_to_cleanup, force=args.force)

    # 显示结果
    print("\n" + "=" * 80)
    if cleaned:
        print(f"✅ 成功清理 {len(cleaned)} 个容器:")
        for container in cleaned:
            print(f"    ✓ {container}")
    else:
        print("⚠️  没有容器被清理（可能所有容器都在运行中，需要 --force 参数）")

    print("=" * 80)
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ 操作被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.exception("清理过程中发生错误: %s", e)
        print(f"\n❌ 错误: {e}")
        sys.exit(1)
