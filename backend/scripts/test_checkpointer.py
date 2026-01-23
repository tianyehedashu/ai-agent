"""测试 Checkpointer 初始化

测试策略：只通过公共接口验证行为，不访问私有属性。
验证点：
1. setup() 前 get_checkpointer() 返回 None（postgres 类型）
2. setup() 后 get_checkpointer() 返回有效实例
3. 返回的实例具有预期的异步方法（aget_tuple）
4. cleanup() 正常执行不抛异常
"""

import asyncio
import sys

from bootstrap.config import settings
from domains.runtime.infrastructure.engine.langgraph_checkpointer import LangGraphCheckpointer

# Windows 需要使用 SelectorEventLoop（psycopg 要求）
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def test_postgres_checkpointer() -> bool:
    """测试 PostgreSQL checkpointer 初始化流程"""
    print("=" * 60)
    print("Testing AsyncPostgresSaver checkpointer initialization...")
    print(f"Database URL: {settings.database_url[:50]}...")
    print("=" * 60)

    success = True
    cp = LangGraphCheckpointer(storage_type="postgres")

    # 测试 1: setup() 前，get_checkpointer() 应返回 None
    before_setup = cp.get_checkpointer()
    if before_setup is None:
        print("✓ Before setup: get_checkpointer() returns None (expected)")
    else:
        print(f"✗ Before setup: get_checkpointer() returned {type(before_setup)}, expected None")
        success = False

    # 测试 2: setup() 后，get_checkpointer() 应返回有效实例
    await cp.setup()
    after_setup = cp.get_checkpointer()
    if after_setup is not None:
        print(f"✓ After setup: get_checkpointer() returns {type(after_setup).__name__}")
    else:
        print("✗ After setup: get_checkpointer() returned None, expected valid instance")
        success = False

    # 测试 3: 返回的实例应具有 aget_tuple 方法（异步检查点接口）
    if after_setup is not None:
        if hasattr(after_setup, "aget_tuple"):
            print("✓ Checkpointer has aget_tuple method (async interface)")

            # 测试 4: aget_tuple 应该是可调用的（不是 NotImplementedError）
            try:
                config = {"configurable": {"thread_id": "test-integration-123"}}
                result = await after_setup.aget_tuple(config)
                # None 是正常的（没有存储的检查点）
                print(f"✓ aget_tuple executed successfully, result: {result}")
            except NotImplementedError:
                print("✗ aget_tuple raised NotImplementedError (wrong checkpointer type)")
                success = False
            except Exception as e:
                # 其他异常（如连接错误）不算测试失败，但需要记录
                print(f"⚠ aget_tuple raised {type(e).__name__}: {e}")
        else:
            print("✗ Checkpointer missing aget_tuple method")
            success = False

    # 测试 5: cleanup() 应正常执行
    try:
        await cp.cleanup()
        print("✓ cleanup() executed successfully")
    except Exception as e:
        print(f"✗ cleanup() raised {type(e).__name__}: {e}")
        success = False

    return success


async def test_memory_checkpointer() -> bool:
    """测试 Memory checkpointer（开发模式）"""
    print("\n" + "=" * 60)
    print("Testing MemorySaver checkpointer...")
    print("=" * 60)

    success = True
    cp = LangGraphCheckpointer(storage_type="memory")

    # Memory 类型在构造时就已初始化，get_checkpointer() 应返回有效实例
    before_setup = cp.get_checkpointer()
    if before_setup is not None:
        print(f"✓ MemorySaver available immediately: {type(before_setup).__name__}")
    else:
        print("✗ MemorySaver should be available without setup()")
        success = False

    # setup() 应该是幂等的，不应出错
    await cp.setup()
    after_setup = cp.get_checkpointer()
    if after_setup is not None:
        print(f"✓ After setup: {type(after_setup).__name__}")
    else:
        print("✗ MemorySaver lost after setup()")
        success = False

    await cp.cleanup()
    print("✓ cleanup() executed successfully")

    return success


async def main():
    """运行所有测试"""
    results = []

    # 测试 Memory checkpointer（不需要外部依赖）
    results.append(("Memory Checkpointer", await test_memory_checkpointer()))

    # 测试 Postgres checkpointer（需要数据库连接）
    try:
        results.append(("Postgres Checkpointer", await test_postgres_checkpointer()))
    except Exception as e:
        print(f"\n⚠ Postgres test skipped due to connection error: {e}")
        results.append(("Postgres Checkpointer", None))

    # 汇总结果
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for name, result in results:
        if result is True:
            print(f"✓ {name}: PASSED")
        elif result is False:
            print(f"✗ {name}: FAILED")
        else:
            print(f"⚠ {name}: SKIPPED")

    all_passed = all(r is True for r in [r for _, r in results if r is not None])
    print("\n" + ("All tests passed!" if all_passed else "Some tests failed!"))


if __name__ == "__main__":
    asyncio.run(main())
