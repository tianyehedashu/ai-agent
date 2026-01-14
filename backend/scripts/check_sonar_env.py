#!/usr/bin/env python3
"""
检查 SonarCloud 扫描所需的环境
支持从 .env 文件读取配置
"""

import os
from pathlib import Path
import platform
import shutil
import sys

try:
    from dotenv import load_dotenv
except ImportError:
    # 如果没有安装 python-dotenv，尝试手动解析 .env 文件
    def load_dotenv(dotenv_path=None):
        """手动加载 .env 文件"""
        if dotenv_path is None:
            # 查找 .env 文件（当前目录或父目录）
            current = Path.cwd()
            for path in [current, current.parent]:
                env_file = path / ".env"
                if env_file.exists():
                    dotenv_path = env_file
                    break

        if dotenv_path and Path(dotenv_path).exists():
            with Path(dotenv_path).open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        # 只在环境变量不存在时设置
                        if key not in os.environ:
                            os.environ[key] = value


def check_sonar_scanner():
    """检查 sonar-scanner 是否已安装"""
    # 首先尝试标准查找
    if shutil.which("sonar-scanner"):
        return True

    # Windows 上尝试查找 .bat 文件
    if platform.system() == "Windows":
        # 尝试查找 sonar-scanner.bat
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            if not path_dir:
                continue
            bat_file = Path(path_dir) / "sonar-scanner.bat"
            if bat_file.exists():
                return True

        # 尝试常见安装路径
        common_paths = [
            Path(os.environ.get("PROGRAMFILES", ""))
            / "sonar-scanner"
            / "bin"
            / "sonar-scanner.bat",
            Path(os.environ.get("PROGRAMFILES(X86)", ""))
            / "sonar-scanner"
            / "bin"
            / "sonar-scanner.bat",
            Path.home() / "sonar-scanner" / "bin" / "sonar-scanner.bat",
        ]
        for path in common_paths:
            if path.exists():
                return True

    print("错误: sonar-scanner 未安装", file=sys.stderr)
    print("请安装: https://docs.sonarqube.org/latest/analysis/scan/sonarscanner/", file=sys.stderr)
    print("Windows 用户建议使用: scripts/sonarcloud-scan.ps1", file=sys.stderr)
    return False


def check_sonar_token():
    """检查 SONAR_TOKEN 环境变量是否已设置（支持从 .env 文件读取）"""
    # 先尝试从 .env 文件加载
    load_dotenv()

    token = os.getenv("SONAR_TOKEN")
    if not token:
        print("错误: SONAR_TOKEN 环境变量未设置", file=sys.stderr)
        print("请设置: export SONAR_TOKEN=your-token", file=sys.stderr)
        print("或在 .env 文件中添加: SONAR_TOKEN=your-token", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    if not check_sonar_scanner():
        sys.exit(1)
    if not check_sonar_token():
        sys.exit(1)
    print("环境检查通过", file=sys.stderr)
