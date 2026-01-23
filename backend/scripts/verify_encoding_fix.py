#!/usr/bin/env python3
"""验证编码修复结果"""
import sys
import io
from pathlib import Path

# 设置标准输出编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 查找所有 Python 文件
backend_dir = Path('.')
python_files = list(backend_dir.rglob('*.py'))

# 排除虚拟环境和缓存目录
exclude_dirs = {'.venv', 'venv', '__pycache__', '.pytest_cache', '.mypy_cache', 'node_modules', 'workspace'}
python_files = [
    f for f in python_files
    if not any(excluded in str(f) for excluded in exclude_dirs)
]

decode_errors = []
replacement_chars = []

for file_path in python_files:
    try:
        content = file_path.read_text(encoding='utf-8')
        if '\ufffd' in content:
            replacement_chars.append(str(file_path))
    except UnicodeDecodeError:
        decode_errors.append(str(file_path))
    except Exception:
        pass  # 忽略其他错误

print('编码修复验证结果:')
print(f'总文件数: {len(python_files)}')
print(f'无法 UTF-8 解码: {len(decode_errors)}')
print(f'包含替换字符: {len(replacement_chars)}')

if decode_errors:
    print('\n无法解码的文件:')
    for f in decode_errors[:10]:
        print(f'  - {f}')

if replacement_chars:
    print('\n包含替换字符的文件:')
    for f in replacement_chars[:10]:
        print(f'  - {f}')

if not decode_errors and not replacement_chars:
    print('\n✓ 所有文件编码正常！')
