#!/usr/bin/env python3
"""
运行 SonarCloud 扫描
支持从 .env 文件读取配置
"""

import os
from pathlib import Path
import platform
import shutil
import subprocess
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


def find_sonar_scanner():
    """查找 sonar-scanner 可执行文件"""
    scanner = shutil.which("sonar-scanner")
    if scanner:
        return scanner

    # Windows 上可能需要在 PATH 中查找 sonar-scanner.bat
    if platform.system() == "Windows":
        # 尝试查找 sonar-scanner.bat
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            if not path_dir:
                continue
            bat_file = Path(path_dir) / "sonar-scanner.bat"
            if bat_file.exists():
                return str(bat_file)

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
                return str(path)

    return None


def main():
    """运行 sonar-scanner"""
    # 从 .env 文件加载配置
    load_dotenv()

    token = os.getenv("SONAR_TOKEN")
    if not token:
        print("错误: SONAR_TOKEN 未设置", file=sys.stderr)
        sys.exit(1)

    # 查找 sonar-scanner
    scanner_cmd = find_sonar_scanner()
    if not scanner_cmd:
        print("错误: 找不到 sonar-scanner", file=sys.stderr)
        print(
            "请安装: https://docs.sonarqube.org/latest/analysis/scan/sonarscanner/", file=sys.stderr
        )
        print("Windows 用户建议使用: scripts/sonarcloud-scan.ps1", file=sys.stderr)
        sys.exit(1)

    org = os.getenv("SONAR_ORGANIZATION")

    # 构建 sonar-scanner 命令
    cmd = [
        scanner_cmd,
        "-Dsonar.host.url=https://sonarcloud.io",
        f"-Dsonar.token={token}",
    ]

    if org:
        cmd.extend(
            [
                f"-Dsonar.organization={org}",
                f"-Dsonar.projectKey={org}_ai-agent-backend",
            ]
        )
        print(f"使用组织: {org}", file=sys.stderr)
    else:
        print("使用配置文件中的组织设置...", file=sys.stderr)

    # 运行 sonar-scanner
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
