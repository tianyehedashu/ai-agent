"""
Code Rule Check Script - 代码规则检查脚本
"""

from pathlib import Path
import sys


def check_architecture():
    """检查架构符合性"""
    print("1. Architecture Check (DDD 4-Layer)")
    print("-" * 50)

    checks = []

    # Presentation layer
    try:
        from domains.identity.presentation.router import router as identity_router  # noqa: F401
        from domains.runtime.presentation.chat_router import router as chat_router  # noqa: F401
        from domains.runtime.presentation.session_router import (
            router as session_router,  # noqa: F401
        )
        checks.append(("✓", "Presentation layer imports OK"))
    except ImportError as e:
        checks.append(("✗", f"Presentation layer import failed: {e}"))

    # Application layer
    try:
        from domains.identity.application.user_use_case import UserUseCase  # noqa: F401
        from domains.runtime.application.chat_use_case import ChatUseCase  # noqa: F401
        from domains.runtime.application.session_use_case import SessionUseCase  # noqa: F401
        checks.append(("✓", "Application layer imports OK"))
    except ImportError as e:
        checks.append(("✗", f"Application layer import failed: {e}"))

    # Domain layer
    try:
        from domains.identity.domain.repositories.user_repository import (
            UserRepository,  # noqa: F401
        )
        from domains.runtime.domain.entities.session import Session  # noqa: F401
        checks.append(("✓", "Domain layer imports OK"))
    except ImportError as e:
        checks.append(("✗", f"Domain layer import failed: {e}"))

    # Infrastructure layer
    try:
        from domains.identity.infrastructure.models.user import User  # noqa: F401
        from domains.runtime.infrastructure.repositories.sqlalchemy_session_repository import (  # noqa: F401
            SQLAlchemySessionRepository,
        )
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
        "runtime/presentation",
        "runtime/application",
        "runtime/domain",
        "runtime/infrastructure",
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
