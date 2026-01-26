"""
Code Rule Check Script - 代码规则检查脚本
"""

import os
from pathlib import Path
import sys

# 设置 UTF-8 编码以支持 Unicode 字符
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def check_architecture():
    """检查架构符合性

    此函数在运行时动态导入各层模块以验证 DDD 4 层架构。
    导入必须在函数内部进行，以便捕获 ImportError 并报告架构问题。
    """
    print("1. Architecture Check (DDD 4-Layer)")
    print("-" * 50)

    checks = []

    # Presentation layer
    # pylint: disable=import-outside-toplevel,unused-import
    # 原因：运行时架构检查，必须在函数内部导入以捕获 ImportError
    try:
        from domains.agent.presentation.chat_router import router as chat_router  # noqa: F401
        from domains.agent.presentation.session_router import (
            router as session_router,  # noqa: F401
        )
        from domains.identity.presentation.router import router as identity_router  # noqa: F401

        checks.append(("✓", "Presentation layer imports OK"))
    except ImportError as e:
        checks.append(("✗", f"Presentation layer import failed: {e}"))

    # Application layer
    # pylint: disable=import-outside-toplevel,unused-import
    try:
        from domains.agent.application.chat_use_case import ChatUseCase  # noqa: F401
        from domains.agent.application.session_use_case import SessionUseCase  # noqa: F401
        from domains.identity.application.user_use_case import UserUseCase  # noqa: F401

        checks.append(("✓", "Application layer imports OK"))
    except ImportError as e:
        checks.append(("✗", f"Application layer import failed: {e}"))

    # Domain layer
    # pylint: disable=import-outside-toplevel,unused-import
    try:
        from domains.agent.domain.entities.session import SessionDomainService  # noqa: F401
        from domains.agent.domain.interfaces.session_repository import (
            SessionRepository,
        )

        checks.append(("✓", "Domain layer imports OK"))
    except ImportError as e:
        checks.append(("✗", f"Domain layer import failed: {e}"))

    # Infrastructure layer
    # pylint: disable=import-outside-toplevel,unused-import
    try:
        from domains.agent.infrastructure.repositories import (  # noqa: F401
            SessionRepository,
        )
        from domains.identity.infrastructure.models.user import User  # noqa: F401

        checks.append(("✓", "Infrastructure layer imports OK"))
    except ImportError as e:
        checks.append(("✗", f"Infrastructure layer import failed: {e}"))

    for status, msg in checks:
        print(f"{status} {msg}")

    return all(status == "✓" for status, _ in checks)


def check_directory_structure():
    """检查目录结构"""
    print("\n2. Directory Structure Check")
    print("-" * 50)

    base_path = Path("domains")
    if not base_path.exists():
        print("✗ domains/ directory not found")
        return False

    required_dirs = [
        "identity/presentation",
        "identity/application",
        "identity/domain",
        "identity/infrastructure",
        "agent/presentation",
        "agent/application",
        "agent/domain",
        "agent/infrastructure",
    ]

    all_exist = True
    for dir_path in required_dirs:
        full_path = base_path / dir_path
        if full_path.exists():
            print(f"✓ {dir_path}/")
        else:
            print(f"✗ {dir_path}/ (missing)")
            all_exist = False

    return all_exist


def check_imports():
    """检查导入是否正"""
    print("\n3. Import Path Check")
    print("-" * 50)

    issues = []

    # 检查是否还有 core. 导入
    python_files = list(Path().rglob("*.py"))
    exclude_dirs = {".venv", "venv", "__pycache__", ".pytest_cache", "workspace"}

    for py_file in python_files:
        if any(excluded in str(py_file) for excluded in exclude_dirs):
            continue
        # 排除脚本自身
        if "check_rules.py" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            if "from core." in content or "import core." in content:
                issues.append(str(py_file))
        except Exception:
            pass  # 忽略无法读取的文件

    if issues:
        print(f"✗ 发现 {len(issues)} 个文件仍使用 core. 导入:")
        for issue in issues[:10]:  # 只显示前10个
            print(f"  - {issue}")
        if len(issues) > 10:
            print(f"  ... 还有 {len(issues) - 10} 个文件")
        return False
    else:
        print("✓ 没有发现 core. 导入")
        return True


def check_app_startup():
    """检查应用能否正常启动"""
    print("\n4. FastAPI App Check")
    print("-" * 50)

    # pylint: disable=import-outside-toplevel,unused-import
    # 原因：运行时检查，必须在函数内部导入以捕获异常
    try:
        from bootstrap.main import app  # noqa: F401

        print("✓ FastAPI app imports OK")
        return True
    except Exception as e:
        print(f"✗ FastAPI app import failed: {e}")
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("        CODE RULE CHECK - DDD 4-Layer")
    print("=" * 50)

    results = []

    results.append(("Architecture", check_architecture()))
    results.append(("Directory Structure", check_directory_structure()))
    results.append(("Imports", check_imports()))
    results.append(("App Startup", check_app_startup()))

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("=" * 50)

    if all_passed:
        print("All checks passed! ✓")
        sys.exit(0)
    else:
        print("Some checks failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
