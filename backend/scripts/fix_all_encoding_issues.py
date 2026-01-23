#!/usr/bin/env python3
"""修复项目中所有 Python 文件的编码问题"""
import io
from pathlib import Path
import re
import sys

# 设置标准输出编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 查找所有 Python 文件
backend_dir = Path()
python_files = list(backend_dir.rglob('*.py'))

# 排除虚拟环境和缓存目录
exclude_dirs = {'.venv', 'venv', '__pycache__', '.pytest_cache', '.mypy_cache', 'node_modules', 'workspace'}
python_files = [
    f for f in python_files
    if not any(excluded in str(f) for excluded in exclude_dirs)
]

fixed_count = 0
error_count = 0
skipped_count = 0

def try_decode_file(file_path: Path) -> tuple[str | None, str | None]:
    """尝试以不同编码读取文件"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'windows-1252', 'latin-1']

    for encoding in encodings:
        try:
            content = file_path.read_text(encoding=encoding, errors='replace')
            return content, encoding
        except (UnicodeDecodeError, LookupError):
            continue

    return None, None

def fix_garbled_chars(content: str) -> str:
    """修复常见的乱码字符"""
    # 替换替换字符 \ufffd
    content = content.replace('\ufffd', '')

    # 修复常见的中文乱码模式
    # 这些模式可能需要根据实际情况调整
    fixes = [
        # 修复 docstring 中的乱码
        (r'([\u4e00-\u9fff]+)[?]+', r'\1'),  # 中文后跟 ? 或替换字符
        (r'[?]+([\u4e00-\u9fff]+)', r'\1'),  # ? 或替换字符后跟中文
    ]

    for pattern, replacement in fixes:
        content = re.sub(pattern, replacement, content)

    return content

for file_path in python_files:
    try:
        # 尝试读取文件
        content, original_encoding = try_decode_file(file_path)

        if content is None:
            print(f'跳过 {file_path}: 无法解码')
            skipped_count += 1
            continue

        # 检查是否需要修复
        needs_fix = False

        # 检查替换字符
        if '\ufffd' in content:
            needs_fix = True

        # 检查编码问题（如果不是 UTF-8）
        if original_encoding != 'utf-8':
            needs_fix = True

        # 检查明显的乱码模式（中文后跟 ?）
        if re.search(r'[\u4e00-\u9fff]+[?]+', content):
            needs_fix = True

        if not needs_fix:
            continue

        # 修复内容
        fixed_content = fix_garbled_chars(content)

        # 以 UTF-8 保存
        file_path.write_text(fixed_content, encoding='utf-8')

        print(f'修复: {file_path} (原编码: {original_encoding})')
        fixed_count += 1

    except Exception as e:
        print(f'错误 {file_path}: {e}')
        error_count += 1

print(f'\n修复完成: {fixed_count} 个文件')
print(f'错误: {error_count} 个文件')
print(f'跳过: {skipped_count} 个文件')
