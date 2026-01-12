"""
基准测试集加载器测试
"""

import pytest
from pathlib import Path

from evaluation.benchmark_loader import (
    get_benchmark_info,
    get_test_cases,
    load_benchmark,
)


class TestBenchmarkLoader:
    """基准测试集加载器测试"""

    @pytest.fixture
    def benchmark_file(self, tmp_path):
        """创建临时基准测试文件"""
        benchmark_data = {
            "benchmark": {
                "name": "Test Benchmark",
                "version": "1.0",
            },
            "test_cases": [
                {
                    "id": "test_001",
                    "input": "Test input",
                    "expected_output": "Test output",
                },
            ],
        }

        import yaml

        file_path = tmp_path / "test_benchmark.yaml"
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(benchmark_data, f)

        return file_path

    def test_load_benchmark(self, benchmark_file):
        """测试: 加载基准测试集"""
        # Act
        data = load_benchmark(benchmark_file)

        # Assert
        assert "benchmark" in data
        assert "test_cases" in data

    def test_load_benchmark_file_not_found(self):
        """测试: 文件不存在时抛出错误"""
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            load_benchmark("non_existent_file.yaml")

    def test_get_test_cases(self, benchmark_file):
        """测试: 获取测试用例"""
        # Arrange
        data = load_benchmark(benchmark_file)

        # Act
        cases = get_test_cases(data)

        # Assert
        assert len(cases) == 1
        assert cases[0]["id"] == "test_001"

    def test_get_benchmark_info(self, benchmark_file):
        """测试: 获取基准测试集信息"""
        # Arrange
        data = load_benchmark(benchmark_file)

        # Act
        info = get_benchmark_info(data)

        # Assert
        assert info["name"] == "Test Benchmark"
        assert info["version"] == "1.0"
