"""
SessionManager 使用示例

展示如何使用重构后的 SessionManager 与工厂模式。
"""

import io
import sys

# 设置标准输出为 UTF-8，解决 Windows 控制台编码问题
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import asyncio

from core.sandbox import (
    DefaultSessionExecutorFactory,
    MockSessionExecutorFactory,
    SessionManager,
    SessionPolicy,
)

# ============================================================================
# 示例 1: 默认使用（生产环境）
# ============================================================================

async def example_default_usage():
    """示例 1：默认使用，自动使用 DefaultSessionExecutorFactory"""
    print("=" * 60)
    print("示例 1: 默认使用")
    print("=" * 60)

    # 不注入工厂，使用默认配置
    manager = SessionManager()
    await manager.start()

    try:
        # 创建会话
        session = await manager.get_or_create_session(
            user_id="user-001",
            conversation_id="conv-001",
        )

        print(f"[OK] 创建会话成功: {session.session_id}")
        print(f"  用户: {session.user_id}")
        print(f"  对话: {session.conversation_id}")
        print(f"  状态: {session.state}")

    finally:
        await manager.stop()


# ============================================================================
# 示例 2: 自定义默认工厂（生产环境）
# ============================================================================

async def example_custom_default_factory():
    """示例 2：自定义默认工厂配置"""
    print("\n" + "=" * 60)
    print("示例 2: 自定义默认工厂")
    print("=" * 60)

    # 创建自定义配置的默认工厂
    factory = DefaultSessionExecutorFactory(
        image="python:3.12-slim",  # 使用 Python 3.12
        workspace_path="/data/ai-agent/workspaces",  # 自定义工作目录
        container_workspace="/workspace",
    )

    # 注入工厂
    policy = SessionPolicy(
        idle_timeout=3600,  # 1 小时
        max_sessions_per_user=3,
    )
    manager = SessionManager(policy=policy, executor_factory=factory)
    await manager.start()

    try:
        session = await manager.get_or_create_session(
            user_id="user-002",
            conversation_id="conv-002",
        )

        print(f"[OK] 使用自定义工厂创建会话: {session.session_id}")
        print("  镜像: python:3.12-slim")
        print("  工作目录: /data/ai-agent/workspaces")

    finally:
        await manager.stop()


# ============================================================================
# 示例 3: 使用 Mock 工厂（单元测试）
# ============================================================================

async def example_mock_factory():
    """示例 3：使用 Mock 工厂进行测试（不启动真实容器）"""
    print("\n" + "=" * 60)
    print("示例 3: Mock 工厂（单元测试）")
    print("=" * 60)

    # 创建 Mock 工厂
    mock_factory = MockSessionExecutorFactory()

    policy = SessionPolicy(idle_timeout=300)
    manager = SessionManager(policy=policy, executor_factory=mock_factory)
    await manager.start()

    try:
        # 创建多个会话
        session1 = await manager.get_or_create_session(
            user_id="test-user",
            conversation_id="test-conv-1",
        )
        session2 = await manager.get_or_create_session(
            user_id="test-user",
            conversation_id="test-conv-2",
        )

        print(f"[OK] 创建模拟会话 1: {session1.session_id}")
        print(f"[OK] 创建模拟会话 2: {session2.session_id}")
        print(f"  工厂跟踪: 共创建 {len(mock_factory.created_executors)} 个执行器")
        print("  说明: 使用 Mock 工厂，未启动真实 Docker 容器")

    finally:
        await manager.stop()


# ============================================================================
# 示例 4: 自定义工厂（高级用法）
# ============================================================================

class MonitoredExecutorFactory:
    """
    带监控的自定义执行器工厂

    示例：在生产环境中添加监控、日志等功能
    """

    def __init__(self):
        self.total_created = 0
        self.active_executors = []

    def create_session_executor(self, max_idle_seconds, config=None):
        """创建执行器并添加监控"""
        from core.sandbox.executor import SessionDockerExecutor

        executor = SessionDockerExecutor(
            image="python:3.11-slim",
            max_idle_seconds=max_idle_seconds,
        )

        # 添加监控
        self.total_created += 1
        self.active_executors.append(executor)

        print(f"  [监控] 创建执行器 #{self.total_created}")
        print(f"  [监控] 当前活跃执行器: {len(self.active_executors)}")

        return executor

    def get_stats(self):
        """获取统计信息"""
        return {
            "total_created": self.total_created,
            "active_count": len(self.active_executors),
        }


async def example_custom_factory():
    """示例 4：自定义工厂（带监控）"""
    print("\n" + "=" * 60)
    print("示例 4: 自定义工厂（带监控）")
    print("=" * 60)

    # 使用自定义工厂
    custom_factory = MonitoredExecutorFactory()
    manager = SessionManager(executor_factory=custom_factory)
    await manager.start()

    try:
        # 创建多个会话
        for i in range(3):
            session = await manager.get_or_create_session(
                user_id=f"user-{i}",
                conversation_id=f"conv-{i}",
            )
            print(f"  创建会话: {session.session_id}")

        # 显示统计
        stats = custom_factory.get_stats()
        print("\n[OK] 工厂统计:")
        print(f"  总共创建: {stats['total_created']} 个执行器")
        print(f"  当前活跃: {stats['active_count']} 个执行器")

    finally:
        await manager.stop()


# ============================================================================
# 示例 5: 会话复用
# ============================================================================

async def example_session_reuse():
    """示例 5：会话复用（同一对话复用容器）"""
    print("\n" + "=" * 60)
    print("示例 5: 会话复用")
    print("=" * 60)

    mock_factory = MockSessionExecutorFactory()
    policy = SessionPolicy(allow_session_reuse=True)
    manager = SessionManager(policy=policy, executor_factory=mock_factory)
    await manager.start()

    try:
        # 第一次获取会话
        session1 = await manager.get_or_create_session(
            user_id="user-reuse",
            conversation_id="conv-reuse",
        )
        print(f"[OK] 首次创建会话: {session1.session_id}")

        # 第二次获取同一对话的会话（应该复用）
        session2 = await manager.get_or_create_session(
            user_id="user-reuse",
            conversation_id="conv-reuse",
        )
        print(f"[OK] 复用会话: {session2.session_id}")

        # 验证是否复用
        if session1.session_id == session2.session_id:
            print("  [OK] 会话复用成功！")
            print(f"  工厂只创建了 {len(mock_factory.created_executors)} 个执行器")
        else:
            print("  [FAIL] 会话未复用")

    finally:
        await manager.stop()


# ============================================================================
# 主函数
# ============================================================================

async def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("SessionManager 工厂模式使用示例")
    print("=" * 60)

    # 运行所有示例
    await example_default_usage()
    await example_custom_default_factory()
    await example_mock_factory()
    await example_custom_factory()
    await example_session_reuse()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    # 注意：示例中使用 Mock 工厂来避免 Docker 依赖
    # 在生产环境中，应该使用 DefaultSessionExecutorFactory
    asyncio.run(main())
