#!/usr/bin/env python3
"""检查项目中所有 Python 文件的编码问题"""
import sys
import io
from pathlib import Path
import re

# 设置标准输出编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 查找所有 Python 文件
backend_dir = Path('.')
python_files = list(backend_dir.rglob('*.py'))

# 排除虚拟环境和缓存目录
exclude_dirs = {'.venv', 'venv', '__pycache__', '.pytest_cache', '.mypy_cache', 'node_modules'}
python_files = [
    f for f in python_files
    if not any(excluded in str(f) for excluded in exclude_dirs)
]

issues = []

for file_path in python_files:
    try:
        # 尝试以 UTF-8 读取文件
        content = file_path.read_text(encoding='utf-8')
        
        # 检查常见的乱码模式
        # 1. 包含替换字符 \ufffd
        if '\ufffd' in content:
            issues.append((str(file_path), '包含替换字符 \\ufffd'))
            continue
        
        # 2. 检查 docstring 或注释中的乱码模式（连续的 ? 或特殊字符）
        # 查找可能的中文注释后跟乱码的情况
        patterns = [
            r'[\u4e00-\u9fff]+[?]+',  # 中文后跟 ? 或替换字符
            r'[?]+[\u4e00-\u9fff]+',  # ? 或替换字符后跟中文
            r'""".*[?].*"""',  # docstring 中包含乱码
            r"'''.*[?].*'''",  # docstring 中包含乱码
            r'#.*[?]',  # 注释中包含乱码
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                issues.append((
                    str(file_path),
                    f'第 {line_num} 行: 可能的乱码模式 "{match.group()[:50]}"'
                ))
                break  # 每个文件只报告一次
                
    except UnicodeDecodeError as e:
        issues.append((str(file_path), f'无法以 UTF-8 解码: {e}'))
    except Exception as e:
        issues.append((str(file_path), f'读取错误: {e}'))

# 输出结果
if issues:
    print(f'发现 {len(issues)} 个可能的编码问题:\n')
    for file_path, issue in issues:
        print(f'{file_path}: {issue}')
else:
    print('未发现编码问题！')
