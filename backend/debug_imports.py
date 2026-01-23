"""
调试脚本：逐步测试每个导入，找出卡死的位置

运行方式
    python debug_imports.py
"""
import sys
import time
import traceback

print("=" * 60)
print("逐步测试导入，找出卡死位)
print("=" * 60)

start = time.time()

tests = [
    ("基础, lambda: __import__("pytest")),
    ("conftest", lambda: __import__("tests.conftest")),
    ("app.config", lambda: __import__("app.config")),
    ("app.config_loader", lambda: __import__("app.config_loader")),
    ("shared.infrastructure.db.vector (可能导入 chromadb/qdrant)", lambda: __import__("shared.infrastructure.db.vector")),
    ("core.llm.embeddings (可能导入 litellm/fastembed)", lambda: __import__("core.llm.embeddings")),
    ("core.llm.gateway (可能导入 litellm)", lambda: __import__("core.llm.gateway")),
    ("langgraph.checkpoint.memory", lambda: __import__("langgraph.checkpoint.memory")),
    ("langgraph.checkpoint.postgres.aio (可能连接数据", lambda: __import__("langgraph.checkpoint.postgres.aio")),
    ("core.engine.langgraph_checkpointer", lambda: __import__("core.engine.langgraph_checkpointer")),
]

for i, (name, import_func) in enumerate(tests, 1):
    print(f"\n[{i}/{len(tests)}] 测试导入: {name}...")
    test_start = time.time()
    
    try:
        # 设置超时0秒）
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"导入 {name} 超时30秒）")
        
        # Windows 不支signal.alarm，使用线程超
        if sys.platform == "win32":
            import threading
            
            result = [None]
            exception = [None]
            
            def do_import():
                try:
                    result[0] = import_func()
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=do_import)
            thread.daemon = True
            thread.start()
            thread.join(timeout=30)
            
            if thread.is_alive():
                print(f"  导入 {name} 超时30秒），可能卡死在这里)
                print(f"    这是最可能的卡死位置！")
                sys.exit(1)
            
            if exception[0]:
                raise exception[0]
            
            module = result[0]
        else:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)
            try:
                module = import_func()
            finally:
                signal.alarm(0)
        
        elapsed = time.time() - test_start
        print(f"  导入成功 ({elapsed:.2f}s)")
        
        if elapsed > 5:
            print(f"    ⚠️  警告：导入耗时较长（{elapsed:.2f}s?)
            
    except TimeoutError as e:
        print(f"  ?{e}")
        print(f"    这是卡死的位置！")
        sys.exit(1)
    except Exception as e:
        print(f"  导入失败: {e}")
        print(f"    堆栈跟踪)
        traceback.print_exc()
        sys.exit(1)

print("\n" + "=" * 60)
print(f"所有导入测试通过！总耗时: {time.time() - start:.2f}s")
print("=" * 60)
print("\n如果所有导入都成功，问题可能在 pytest 收集阶段的其他操作)
print("建议检查：")
print("  1. pytest 插件初始)
print("  2. conftest.py 中的 fixture 定义")
print("  3. 测试文件的模块级代码执行")
