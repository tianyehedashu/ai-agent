#!/usr/bin/env python3
"""迁移 core/ 导入路径到新位置的脚本。"""

import re
from pathlib import Path

# 定义替换规则
REPLACEMENTS = [
    # runtime infrastructure
    (r"from core\.engine\.", "from domains.runtime.infrastructure.engine."),
    (r"from core\.engine import", "from domains.runtime.infrastructure.engine import"),
    (r"from core\.memory\.", "from domains.runtime.infrastructure.memory."),
    (r"from core\.memory import", "from domains.runtime.infrastructure.memory import"),
    (r"from core\.sandbox\.", "from domains.runtime.infrastructure.sandbox."),
    (r"from core\.sandbox import", "from domains.runtime.infrastructure.sandbox import"),
    (r"from core\.reasoning\.", "from domains.runtime.infrastructure.reasoning."),
    (r"from core\.reasoning import", "from domains.runtime.infrastructure.reasoning import"),
    (r"from core\.routing\.", "from domains.runtime.infrastructure.routing."),
    (r"from core\.routing import", "from domains.runtime.infrastructure.routing import"),
    (r"from core\.context\.", "from domains.runtime.infrastructure.context."),
    (r"from core\.context import", "from domains.runtime.infrastructure.context import"),
    # studio infrastructure
    (r"from core\.studio\.", "from domains.studio.infrastructure.studio."),
    (r"from core\.studio import", "from domains.studio.infrastructure.studio import"),
    (r"from core\.quality\.", "from domains.studio.infrastructure.quality."),
    (r"from core\.quality import", "from domains.studio.infrastructure.quality import"),
    (r"from core\.lsp\.", "from domains.studio.infrastructure.lsp."),
    (r"from core\.lsp import", "from domains.studio.infrastructure.lsp import"),
    # shared infrastructure
    (r"from core\.llm\.", "from shared.infrastructure.llm."),
    (r"from core\.llm import", "from shared.infrastructure.llm import"),
    (r"from core\.config\.", "from shared.infrastructure.config."),
    (r"from core\.config import", "from shared.infrastructure.config import"),
    (r"from core\.auth\.", "from shared.infrastructure.auth."),
    (r"from core\.auth import", "from shared.infrastructure.auth import"),
    (r"from core\.observability\.", "from shared.infrastructure.observability."),
    (r"from core\.observability import", "from shared.infrastructure.observability import"),
    (r"from core\.utils\.", "from shared.infrastructure.utils."),
    (r"from core\.utils import", "from shared.infrastructure.utils import"),
    (r"from core\.a2a\.", "from shared.infrastructure.a2a."),
    (r"from core\.a2a import", "from shared.infrastructure.a2a import"),
    # shared root
    (r"from core\.interfaces import", "from shared.interfaces import"),
    (r"from core\.types import", "from shared.types import"),
]


def migrate_file(filepath: Path) -> bool:
    """迁移单个文件的导入路径。返回是否有修改。"""
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"  [SKIP] 无法读取（编码问题）: {filepath}")
        return False
    
    original = content
    for pattern, replacement in REPLACEMENTS:
        content = re.sub(pattern, replacement, content)
    
    if content != original:
        filepath.write_text(content, encoding="utf-8")
        return True
    return False


def main():
    """主函数。"""
    backend_dir = Path(__file__).parent.parent
    
    # 排除目录
    exclude_dirs = {".venv", "__pycache__", ".git", "node_modules"}
    
    modified_files = []
    total_files = 0
    
    for py_file in backend_dir.rglob("*.py"):
        # 跳过排除目录
        if any(part in exclude_dirs for part in py_file.parts):
            continue
        
        total_files += 1
        if migrate_file(py_file):
            modified_files.append(py_file)
            print(f"  [OK] {py_file.relative_to(backend_dir)}")
    
    print(f"\n完成! 共扫描 {total_files} 个文件，修改了 {len(modified_files)} 个文件。")


if __name__ == "__main__":
    main()
