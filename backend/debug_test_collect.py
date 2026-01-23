"""
调试脚本：测pytest 收集阶段是否卡死

运行方式
    python debug_test_collect.py
"""
import sys
import time

print("=" * 60)
print("开始测试导..")
print("=" * 60)

start = time.time()

# 1. 测试基础导入
print("\n[1/5] 导入基础模块...")
try:
    import pytest
    print(f"  ?pytest 导入成功 ({time.time() - start:.2f}s)")
except Exception as e:
    print(f"  ?pytest 导入失败: {e}")
    sys.exit(1)

# 2. 测试 conftest 导入
print("\n[2/5] 导入 conftest...")
try:
    import tests.conftest
    print(f"  ?conftest 导入成功 ({time.time() - start:.2f}s)")
except Exception as e:
    print(f"  ?conftest 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. 测试 config 导入
print("\n[3/5] 导入 app.config...")
try:
    from bootstrap.config import settings
    print(f"  ?config 导入成功 ({time.time() - start:.2f}s)")
except Exception as e:
    print(f"  ?config 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 测试 LLM 模块导入（不实例化）
print("\n[4/5] 导入 core.llm (延迟导入)...")
try:
    from shared.infrastructure.llm import LLMGateway
    print(f"  ?core.llm 导入成功 ({time.time() - start:.2f}s)")
    print(f"    注意：这只是延迟导入，不会触litellm 初始)
except Exception as e:
    print(f"  ?core.llm 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. 测试 pytest 收集
print("\n[5/5] 测试 pytest 收集（不运行测试..")
try:
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "not e2e"],
        capture_output=True,
        text=True,
        timeout=30,  # 30 秒超
    )
    if result.returncode == 0:
        print(f"  ?pytest 收集成功 ({time.time() - start:.2f}s)")
        print(f"    收集{len([l for l in result.stdout.split('\\n') if 'test_' in l])} 个测)
    else:
        print(f"  ?pytest 收集失败 (返回 {result.returncode})")
        print(f"    stdout: {result.stdout[:500]}")
        print(f"    stderr: {result.stderr[:500]}")
except subprocess.TimeoutExpired:
    print(f"  ?pytest 收集超时30秒），可能卡)
    sys.exit(1)
except Exception as e:
    print(f"  ?pytest 收集异常: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print(f"所有测试通过！总耗时: {time.time() - start:.2f}s")
print("=" * 60)
