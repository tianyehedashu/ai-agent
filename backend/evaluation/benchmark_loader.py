"""
基准测试集加载器

从 YAML 文件加载基准测试用例
"""

from pathlib import Path
from typing import Any

import yaml


def load_benchmark(file_path: str | Path) -> dict[str, Any]:
    """
    加载基准测试集

    Args:
        file_path: YAML 文件路径

    Returns:
        基准测试集配置
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {file_path}")

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data


def get_test_cases(benchmark_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    从基准测试集中提取测试用例

    Args:
        benchmark_data: 基准测试集数据

    Returns:
        测试用例列表
    """
    return benchmark_data.get("test_cases", [])


def get_benchmark_info(benchmark_data: dict[str, Any]) -> dict[str, Any]:
    """
    获取基准测试集信息

    Args:
        benchmark_data: 基准测试集数据

    Returns:
        基准测试集信息
    """
    return benchmark_data.get("benchmark", {})
